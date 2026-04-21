"""
EmailDialog — modal dialog for composing and sending conflict-of-interest
email reports from the Sacramento County CoI Dashboard.

Opens as a CTkToplevel window.  All SMTP work runs in a background thread
so the Tkinter main loop is never blocked.
"""

import smtplib
import threading
from datetime import datetime

import customtkinter as ctk

from core.email_config import config_exists, load as load_config, save as save_config
from core.email_sender import EmailSender
from ui.theme import COLORS


class EmailDialog(ctk.CTkToplevel):
    """
    Compose and send a Conflict-of-Interest email report.

    Parameters
    ----------
    parent :
        The parent Tk/CTk widget (typically the root window).
    records : list[dict]
        Currently filtered/selected conflict records to include in the report.
    officials : list[str]
        Official names extracted from those records (used to pre-populate
        the To field as a hint; user must replace with an actual email address).
    """

    def __init__(
        self,
        parent,
        records: list,
        officials: list,
    ) -> None:
        super().__init__(parent)
        self._records   = records
        self._officials = officials

        self._smtp_visible = False  # toggles the SMTP settings panel

        self._configure_window()
        self._build_ui()
        self._populate_defaults()

        self.grab_set()  # modal
        self.focus_force()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _configure_window(self) -> None:
        self.title("Email Conflict-of-Interest Report")
        self.geometry("780x760")
        self.minsize(640, 580)
        self.configure(fg_color=COLORS["bg_primary"])
        self.resizable(True, True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ── Title bar ────────────────────────────────────────────────
        title_bar = ctk.CTkFrame(
            self, fg_color=COLORS["bg_secondary"], corner_radius=0, height=48
        )
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_propagate(False)
        ctk.CTkLabel(
            title_bar,
            text="  SEND EMAIL REPORT",
            font=ctk.CTkFont("Andale Mono", 14, "bold"),
            text_color=COLORS["accent_green"],
        ).pack(side="left", padx=16, pady=12)

        # ── Scrollable body ───────────────────────────────────────────
        body_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_primary"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["text_muted"],
        )
        body_scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        body_scroll.grid_columnconfigure(0, weight=1)

        pad = {"padx": 20, "pady": (0, 10)}

        # ── To ────────────────────────────────────────────────────────
        self._field_label(body_scroll, "To (email address)")
        self._to_entry = self._entry(body_scroll)
        self._to_entry.pack(fill="x", **pad)

        # ── Subject ───────────────────────────────────────────────────
        self._field_label(body_scroll, "Subject")
        self._subject_entry = self._entry(body_scroll)
        self._subject_entry.pack(fill="x", **pad)

        # ── Body ─────────────────────────────────────────────────────
        self._field_label(body_scroll, "Body (editable)")
        self._body_box = ctk.CTkTextbox(
            body_scroll,
            height=280,
            font=ctk.CTkFont("Andale Mono", 10),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            wrap="word",
            corner_radius=6,
        )
        self._body_box.pack(fill="x", padx=20, pady=(0, 16))

        # ── SMTP settings (collapsible) ───────────────────────────────
        smtp_toggle_row = ctk.CTkFrame(body_scroll, fg_color="transparent")
        smtp_toggle_row.pack(fill="x", padx=20, pady=(0, 4))
        smtp_toggle_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            smtp_toggle_row,
            text="SMTP SETTINGS",
            font=ctk.CTkFont("Andale Mono", 9, "bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkFrame(
            smtp_toggle_row, fg_color=COLORS["border"], height=1
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(2, 0))

        self._smtp_toggle_btn = ctk.CTkButton(
            smtp_toggle_row,
            text="Show",
            font=ctk.CTkFont("Andale Mono", 9),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            width=52,
            height=22,
            corner_radius=4,
            command=self._toggle_smtp_panel,
        )
        self._smtp_toggle_btn.grid(row=0, column=2, padx=(8, 0))

        # Collapsible frame (hidden by default)
        self._smtp_frame = ctk.CTkFrame(
            body_scroll,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=6,
        )
        # Do NOT pack here — toggled by _toggle_smtp_panel

        inner = ctk.CTkFrame(self._smtp_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        inner.grid_columnconfigure((0, 1), weight=1)

        # Row 0: Host | Port
        ctk.CTkLabel(
            inner,
            text="SMTP Host",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        ctk.CTkLabel(
            inner,
            text="Port",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        self._host_entry = self._entry(inner, placeholder="smtp.gmail.com")
        self._host_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self._port_entry = self._entry(inner, placeholder="587")
        self._port_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        # Row 2: From email | App password
        ctk.CTkLabel(
            inner,
            text="From Email",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=2, column=0, sticky="w", pady=(0, 2))
        ctk.CTkLabel(
            inner,
            text="App Password",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        self._from_entry = self._entry(inner, placeholder="you@gmail.com")
        self._from_entry.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        self._pw_entry = self._entry(inner, placeholder="xxxx xxxx xxxx xxxx", show="*")
        self._pw_entry.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        # "Save Settings" button
        ctk.CTkButton(
            inner,
            text="Save Settings",
            font=ctk.CTkFont("Andale Mono", 11, "bold"),
            fg_color=COLORS["accent_purple"],
            hover_color="#7c4fc4",
            text_color="#ffffff",
            height=30,
            corner_radius=6,
            command=self._save_smtp_settings,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        # Hint label about Gmail App Passwords
        ctk.CTkLabel(
            inner,
            text=(
                "Gmail users: enable 2-Step Verification, then create an App Password at\n"
                "myaccount.google.com/apppasswords — use that 16-char code above."
            ),
            font=ctk.CTkFont("Andale Mono", 9),
            text_color=COLORS["text_muted"],
            justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ── Bottom button bar ─────────────────────────────────────────
        btn_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0)
        btn_bar.grid(row=2, column=0, sticky="ew")
        btn_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_bar,
            text="Send Email",
            font=ctk.CTkFont("Andale Mono", 12, "bold"),
            fg_color=COLORS["accent_purple"],
            hover_color="#7c4fc4",
            text_color="#ffffff",
            height=36,
            corner_radius=6,
            command=self._on_send,
        ).grid(row=0, column=0, padx=(16, 6), pady=12, sticky="w")

        ctk.CTkButton(
            btn_bar,
            text="Cancel",
            font=ctk.CTkFont("Andale Mono", 12),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            height=36,
            corner_radius=6,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(0, 16), pady=12, sticky="w")

        self._status_lbl = ctk.CTkLabel(
            btn_bar,
            text="",
            font=ctk.CTkFont("Andale Mono", 11),
            text_color=COLORS["text_secondary"],
        )
        self._status_lbl.grid(row=0, column=2, padx=16, pady=12, sticky="e")

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    def _field_label(self, parent, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(anchor="w", padx=20, pady=(8, 2))

    def _entry(self, parent, placeholder: str = "", show: str = "") -> ctk.CTkEntry:
        kwargs = dict(
            font=ctk.CTkFont("Andale Mono", 11),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_muted"],
            height=32,
            corner_radius=6,
        )
        if placeholder:
            kwargs["placeholder_text"] = placeholder
        if show:
            kwargs["show"] = show
        return ctk.CTkEntry(parent, **kwargs)

    # ------------------------------------------------------------------
    # Default content
    # ------------------------------------------------------------------

    def _populate_defaults(self) -> None:
        # To: pre-fill with first official name as a hint
        first_official = self._officials[0] if self._officials else ""
        self._to_entry.insert(0, first_official)

        # Subject
        n = len(self._records)
        self._subject_entry.insert(
            0, f"Conflict of Interest Report — Sacramento County — {n} Records"
        )

        # Body
        body = self._build_body_text()
        self._body_box.insert("1.0", body)

        # Pre-populate SMTP fields if config exists
        if config_exists():
            try:
                cfg = load_config()
                self._host_entry.insert(0, cfg.get("smtp_host", "smtp.gmail.com"))
                self._port_entry.insert(0, str(cfg.get("smtp_port", 587)))
                self._from_entry.insert(0, cfg.get("sender_email", ""))
                # Do NOT pre-fill password — user re-enters for security
            except Exception:
                pass
        else:
            self._host_entry.insert(0, "smtp.gmail.com")
            self._port_entry.insert(0, "587")

    def _build_body_text(self) -> str:
        records  = self._records
        n        = len(records)

        high_count   = sum(
            1 for r in records
            if r.get("conflict", {}).get("confidence", "") == "high"
        )
        medium_count = sum(
            1 for r in records
            if r.get("conflict", {}).get("confidence", "") == "medium"
        )
        low_count    = sum(
            1 for r in records
            if r.get("conflict", {}).get("confidence", "") == "low"
        )

        lines = [
            "SACRAMENTO COUNTY — CONFLICT OF INTEREST REPORT",
            "================================================",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Records included: {n}",
            "",
            "SUMMARY",
            "-------",
            f"High Confidence:   {high_count}",
            f"Medium Confidence: {medium_count}",
            f"Low Confidence:    {low_count}",
            "",
            "FLAGGED RECORDS",
            "---------------",
        ]

        display_records = records[:20]
        for rec in display_records:
            conflict = rec.get("conflict", {})
            source   = rec.get("source",   {})
            f700     = rec.get("form700",   {})

            conf      = conflict.get("confidence", "unknown")
            src_file  = source.get("file",  "unknown")
            page      = source.get("page",  "?")
            officials = f700.get("officials", [])
            entities  = f700.get("entities",  [])
            reasoning = conflict.get("reasoning", "")

            lines.append(f"[{conf.upper()}] {src_file} — Page {page}")
            lines.append(f"Officials: {', '.join(officials) if officials else 'None identified'}")
            lines.append(f"Entities:  {', '.join(entities)  if entities  else 'None identified'}")
            reasoning_snippet = reasoning[:300] + "..." if len(reasoning) > 300 else reasoning
            lines.append(f"Reasoning: {reasoning_snippet}")
            lines.append("---")

        if n > 20:
            lines.append(
                f"... and {n - 20} more records. "
                "Use CSV/PDF export for full dataset."
            )

        lines.extend([
            "",
            "This report was generated by the Sacramento County CoI Dashboard.",
        ])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # SMTP panel toggle
    # ------------------------------------------------------------------

    def _toggle_smtp_panel(self) -> None:
        self._smtp_visible = not self._smtp_visible
        if self._smtp_visible:
            self._smtp_frame.pack(fill="x", padx=20, pady=(4, 14))
            self._smtp_toggle_btn.configure(text="Hide")
        else:
            self._smtp_frame.pack_forget()
            self._smtp_toggle_btn.configure(text="Show")

    # ------------------------------------------------------------------
    # Save SMTP settings
    # ------------------------------------------------------------------

    def _save_smtp_settings(self) -> None:
        host = self._host_entry.get().strip()
        port = self._port_entry.get().strip()
        frm  = self._from_entry.get().strip()
        pw   = self._pw_entry.get()

        if not host or not port or not frm:
            self._set_status("Fill in Host, Port, and From Email to save.", COLORS["warning"])
            return

        try:
            port_int = int(port)
        except ValueError:
            self._set_status("Port must be a number (e.g. 587).", COLORS["danger"])
            return

        try:
            save_config({
                "smtp_host":       host,
                "smtp_port":       port_int,
                "sender_email":    frm,
                "sender_password": pw,
            })
            self._set_status("SMTP settings saved.", COLORS["success"])
        except Exception as exc:
            self._set_status(f"Save failed: {exc}", COLORS["danger"])

    # ------------------------------------------------------------------
    # Send email
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        to      = self._to_entry.get().strip()
        subject = self._subject_entry.get().strip()
        body    = self._body_box.get("1.0", "end").strip()

        # Basic validation
        if "@" not in to or "." not in to.split("@")[-1]:
            self._set_status("Please enter a valid email address in the To field.", COLORS["danger"])
            return

        if not subject:
            self._set_status("Subject cannot be empty.", COLORS["warning"])
            return

        # Gather SMTP config — prefer panel fields if visible and populated,
        # otherwise fall back to saved config.
        try:
            smtp_cfg = self._gather_smtp_config()
        except Exception as exc:
            self._set_status(f"SMTP config error: {exc}", COLORS["danger"])
            return

        self._set_status("Sending...", COLORS["accent_purple"])

        html_body = self._text_to_html(body)

        def _worker():
            try:
                sender = EmailSender(
                    smtp_host      = smtp_cfg["smtp_host"],
                    smtp_port      = smtp_cfg["smtp_port"],
                    sender_email   = smtp_cfg["sender_email"],
                    sender_password = smtp_cfg["sender_password"],
                )
                sender.send_html(to, subject, html_body)
                self.after(0, self._on_send_success)
            except smtplib.SMTPAuthenticationError:
                self.after(
                    0,
                    lambda: self._set_status(
                        "Authentication failed. For Gmail, create an App Password at "
                        "myaccount.google.com/apppasswords and use it instead of your "
                        "account password.",
                        COLORS["danger"],
                    ),
                )
            except Exception as exc:
                err_msg = str(exc)
                self.after(
                    0,
                    lambda m=err_msg: self._set_status(f"Error: {m}", COLORS["danger"]),
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _gather_smtp_config(self) -> dict:
        """
        Return the SMTP config to use for sending.

        If the SMTP panel is visible and the user has filled in fields, use
        those values directly (useful before saving).  Otherwise load from
        the persisted config file.
        """
        if self._smtp_visible:
            host = self._host_entry.get().strip()
            port = self._port_entry.get().strip()
            frm  = self._from_entry.get().strip()
            pw   = self._pw_entry.get()
            if host and port and frm and pw:
                try:
                    return {
                        "smtp_host":       host,
                        "smtp_port":       int(port),
                        "sender_email":    frm,
                        "sender_password": pw,
                    }
                except ValueError:
                    pass  # fall through to saved config

        # Try saved config
        if config_exists():
            return load_config()

        raise ValueError(
            "No SMTP settings found. Open the SMTP Settings panel and "
            "fill in your server details, then click Save Settings."
        )

    def _on_send_success(self) -> None:
        self._set_status("Sent successfully", COLORS["success"])
        self.after(2000, self.destroy)

    # ------------------------------------------------------------------
    # HTML conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _text_to_html(text: str) -> str:
        """
        Convert plain text to a dark-themed HTML email body.

        - Newlines become <br>
        - Lines starting with '[HIGH]', '[MEDIUM]', '[LOW]' get color spans
        - Wrapped in a dark-background HTML skeleton
        """
        import html as html_lib

        escaped = html_lib.escape(text)

        # Colour-code confidence tags
        colour_map = {
            "[HIGH]":   "#e05878",
            "[MEDIUM]": "#b07af5",
            "[LOW]":    "#34c97a",
        }
        for tag, colour in colour_map.items():
            escaped = escaped.replace(
                tag,
                f'<span style="color:{colour};font-weight:bold;">{tag}</span>',
            )

        # Convert newlines → <br>
        escaped = escaped.replace("\n", "<br>\n")

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      background-color: #0d1117;
      color: #c9d1d9;
      font-family: "Courier New", Courier, monospace;
      font-size: 13px;
      line-height: 1.6;
      padding: 24px;
      margin: 0;
    }}
    .container {{
      max-width: 760px;
      margin: 0 auto;
      background-color: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 28px 32px;
    }}
    .header {{
      border-bottom: 2px solid #9d6fe8;
      padding-bottom: 12px;
      margin-bottom: 20px;
    }}
    .header-title {{
      color: #9d6fe8;
      font-size: 16px;
      font-weight: bold;
      letter-spacing: 0.05em;
    }}
    .footer {{
      margin-top: 24px;
      padding-top: 12px;
      border-top: 1px solid #30363d;
      color: #484f58;
      font-size: 11px;
    }}
    pre, code {{
      background: #1c2128;
      border-radius: 4px;
      padding: 2px 6px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-title">
        SACRAMENTO COUNTY — CONFLICT OF INTEREST DASHBOARD
      </div>
    </div>
    <div class="content">
      {escaped}
    </div>
    <div class="footer">
      Generated by the Sacramento County CoI Dashboard.
      This message contains flagged conflict-of-interest records from
      Board of Supervisors agenda analysis.
    </div>
  </div>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Status label helper
    # ------------------------------------------------------------------

    def _set_status(self, message: str, color: str = "") -> None:
        kw: dict = {"text": message}
        if color:
            kw["text_color"] = color
        self._status_lbl.configure(**kw)
