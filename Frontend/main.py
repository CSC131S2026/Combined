"""
Entry point — Sacramento County Conflict of Interest Dashboard
Run:  python main.py
"""

import customtkinter as ctk
from app import ConflictDashboard


def main() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    ConflictDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
