"""
FilterEngine — applies filter state to records and computes aggregates.
"""

from collections import Counter, defaultdict


class FilterEngine:
    """Stateless helper that filters records and computes aggregate statistics."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, records: list, filters: dict) -> list:
        """
        Filter records according to the filters dict.

        filters keys (all optional / nullable):
          confidence  — list[str] of levels to include, e.g. ["high", "medium"]
                        or None / [] to include all
          official    — str partial match against form700.officials, or None
          entity      — str partial match against form700.entities, or None
          keyword     — str partial match against keywords_matched, or None
          match_only  — bool; if True, only include records where conflict.match is True
        """
        if not filters:
            return records

        conf_filter = filters.get("confidence")  # list or None
        official    = (filters.get("official") or "").strip().lower()
        entity      = (filters.get("entity")   or "").strip().lower()
        keyword     = (filters.get("keyword")  or "").strip().lower()
        match_only  = filters.get("match_only", False)

        out = []
        for rec in records:
            conflict = rec.get("conflict", {})
            form700  = rec.get("form700",  {})

            # --- match_only filter ---
            if match_only and not conflict.get("match", False):
                continue

            # --- confidence filter ---
            if conf_filter:
                rec_conf = (conflict.get("confidence") or "").lower()
                if rec_conf not in [c.lower() for c in conf_filter]:
                    continue

            # --- official filter ---
            if official:
                officials = [o.lower() for o in form700.get("officials", [])]
                if not any(official in o for o in officials):
                    continue

            # --- entity filter ---
            if entity:
                entities = [e.lower() for e in form700.get("entities", [])]
                if not any(entity in e for e in entities):
                    continue

            # --- keyword filter ---
            if keyword:
                kws = [k.lower() for k in rec.get("keywords_matched", [])]
                if not any(keyword in k for k in kws):
                    continue

            out.append(rec)

        return out

    # ------------------------------------------------------------------

    def compute_aggregates(self, records: list) -> dict:
        """
        Compute summary statistics over a list of records.

        Returns dict with:
          total             — int
          flagged           — int (match == True)
          by_confidence     — {high: int, medium: int, low: int}
          officials_counts  — {name: count}
          entities_counts   — {name: count}
          keywords_freq     — {keyword: count}
          top_files         — [(filename, count)] sorted desc, top 10
        """
        total   = len(records)
        flagged = 0
        by_conf: Counter = Counter()
        officials_c: Counter = Counter()
        entities_c:  Counter = Counter()
        keywords_c:  Counter = Counter()
        files_c:     Counter = Counter()

        for rec in records:
            conflict = rec.get("conflict", {})
            form700  = rec.get("form700",  {})
            source   = rec.get("source",   {})

            if conflict.get("match", False):
                flagged += 1

            conf = (conflict.get("confidence") or "unknown").lower()
            by_conf[conf] += 1

            for o in form700.get("officials", []):
                if o:
                    officials_c[o] += 1

            for e in form700.get("entities", []):
                if e:
                    entities_c[e] += 1

            for k in rec.get("keywords_matched", []):
                if k:
                    keywords_c[k] += 1

            fname = source.get("file", "")
            if fname:
                files_c[fname] += 1

        top_files = files_c.most_common(10)

        return {
            "total":            total,
            "flagged":          flagged,
            "by_confidence": {
                "high":   by_conf.get("high",   0),
                "medium": by_conf.get("medium", 0),
                "low":    by_conf.get("low",    0),
            },
            "officials_counts": dict(officials_c),
            "entities_counts":  dict(entities_c),
            "keywords_freq":    dict(keywords_c),
            "top_files":        top_files,
        }
