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
          official    — str partial match against extracted official labels, or None
          entity      — str partial match against extracted entity labels, or None
          keyword     — str partial match against keywords_matched, or None
          match_only  — bool; if True, only include records where conflict.match is True
        """
        if not filters:
            return records

        conf_filter = filters.get("confidence")  # list or None
        official    = self._normalize_label(filters.get("official") or "").lower()
        entity      = self._normalize_label(filters.get("entity") or "").lower()
        keyword     = self._normalize_label(filters.get("keyword") or "").lower()
        match_only  = filters.get("match_only", False)

        out = []
        for rec in records:
            conflict = rec.get("conflict", {})

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
                officials = [
                    self._normalize_label(name).lower()
                    for name in self.extract_official_names(rec)
                ]
                if not any(official in o for o in officials):
                    continue

            # --- entity filter ---
            if entity:
                entities = [
                    self._normalize_label(name).lower()
                    for name in self.extract_entity_names(rec)
                ]
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
        official_labels: dict[str, str] = {}
        entity_labels: dict[str, str] = {}

        for rec in records:
            conflict = rec.get("conflict", {})
            source   = rec.get("source",   {})

            if conflict.get("match", False):
                flagged += 1

            conf = (conflict.get("confidence") or "unknown").lower()
            by_conf[conf] += 1

            for official in self.extract_official_names(rec):
                key = official.casefold()
                official_labels.setdefault(key, official)
                officials_c[key] += 1

            for entity in self.extract_entity_names(rec):
                key = entity.casefold()
                entity_labels.setdefault(key, entity)
                entities_c[key] += 1

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
            "officials_counts": {
                official_labels[key]: count
                for key, count in sorted(officials_c.items(), key=lambda item: official_labels[item[0]].casefold())
            },
            "entities_counts": {
                entity_labels[key]: count
                for key, count in sorted(entities_c.items(), key=lambda item: entity_labels[item[0]].casefold())
            },
            "keywords_freq":    dict(keywords_c),
            "top_files":        top_files,
        }

    # ------------------------------------------------------------------
    # Shared label extraction
    # ------------------------------------------------------------------

    def extract_official_names(self, rec: dict) -> list[str]:
        names = list(rec.get("form700", {}).get("officials", []))
        names.extend(self._extract_attribution_names(rec, kinds={"person", "role"}))
        return self._dedupe_labels(names)

    def extract_entity_names(self, rec: dict) -> list[str]:
        names = list(rec.get("form700", {}).get("entities", []))
        names.extend(self._extract_attribution_names(rec, kinds={"entity"}))
        return self._dedupe_labels(names)

    def _extract_attribution_names(self, rec: dict, kinds: set[str]) -> list[str]:
        out: list[str] = []
        attribution = rec.get("attribution", {})
        items = [attribution.get("primary_party")] + list(attribution.get("candidates", []) or [])

        for item in items:
            if not isinstance(item, dict):
                continue
            label = self._normalize_label(item.get("name", ""))
            kind = (item.get("type") or "").strip().lower()
            role = self._normalize_label(item.get("role", ""))
            source = (item.get("source") or "").strip().lower()
            if not label or kind not in kinds:
                continue

            if kind == "person":
                if self._is_person_like_official_name(label, role, source):
                    out.append(label)
                continue

            if kind == "role" and self._is_official_role_name(label):
                out.append(label)
                continue

            if kind == "entity":
                out.append(label)

        return out

    @staticmethod
    def _dedupe_labels(labels: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in labels:
            label = FilterEngine._normalize_label(raw)
            if not label:
                continue
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
        return out

    @staticmethod
    def _normalize_label(value: str) -> str:
        return " ".join((value or "").split())

    @classmethod
    def _is_person_like_official_name(cls, name: str, role: str, source: str) -> bool:
        role_l = role.casefold()
        if source == "form700_entity":
            return True
        if any(keyword in role_l for keyword in cls._official_role_keywords()):
            return True
        return cls._looks_like_person_name(name)

    @staticmethod
    def _official_role_keywords() -> tuple[str, ...]:
        return (
            "board",
            "supervisor",
            "executive",
            "director",
            "chief",
            "chair",
            "commission",
            "counsel",
            "attorney",
            "sheriff",
            "clerk",
            "manager",
            "administrator",
            "commissioner",
            "registrar",
            "coroner",
            "defender",
            "probation",
            "officer",
            "planning",
        )

    @classmethod
    def _is_official_role_name(cls, name: str) -> bool:
        label = name.casefold()
        return any(keyword in label for keyword in cls._official_role_keywords())

    @staticmethod
    def _looks_like_person_name(name: str) -> bool:
        blocked_words = {
            "activity", "agreement", "board", "clerk", "comments", "commission",
            "compliance", "consultant", "consultants", "contract", "county",
            "department", "district", "facts", "house", "office", "program",
            "project", "report", "reporter", "services", "supervisor", "witness",
        }
        stopwords = {"a", "an", "and", "for", "from", "in", "of", "on", "or", "the", "to", "under", "with"}

        if not name or "@" in name or any(ch.isdigit() for ch in name):
            return False

        raw_tokens = [token.strip(".,;:()<>[]{}\"'") for token in name.split()]
        tokens = [token for token in raw_tokens if token]
        if not 2 <= len(tokens) <= 4:
            return False

        stopword_hits = sum(token.casefold() in stopwords for token in tokens)
        if stopword_hits > 1:
            return False

        if any(token.casefold() in blocked_words for token in tokens):
            return False

        valid_tokens = 0
        for token in tokens:
            if len(token) > 20:
                return False
            if token.isupper() and len(token) > 3:
                return False
            if token[:1].isalpha() and token[:1].isupper():
                valid_tokens += 1

        return valid_tokens >= 2
