"""Query expansion service for improving search recall."""

import logging
import re
from typing import List, Set, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryExpander:
    """Expands user queries with synonyms, related terms, and learned variations."""

    def __init__(self):
        """Initialize query expander."""
        self.logger = logging.getLogger(__name__)
        self._expansion_cache = {}  # Cache expansions: term -> [expanded_terms]
        self._cache_time = None

    def expand_query(
        self, query: str, project_key: Optional[str] = None, max_expansions: int = 5
    ) -> Tuple[Set[str], Dict[str, List[str]]]:
        """Expand query with synonyms, acronyms, and related terms.

        Args:
            query: Original search query
            project_key: Optional project context for project-specific expansions
            max_expansions: Maximum number of expansions per term

        Returns:
            Tuple of (all_terms_set, expansion_map)
            - all_terms_set: Set of all terms including originals and expansions
            - expansion_map: Dict mapping original_term -> [expanded_terms]
        """
        # Tokenize query into words
        query_terms = self._tokenize(query)

        all_terms = set(query_terms)  # Start with original terms
        expansion_map = {}

        # Load expansions from database
        expansions_db = self._load_expansions(project_key)

        # Expand each term
        for term in query_terms:
            term_lower = term.lower()

            # Get expansions for this term
            expanded = self._get_expansions_for_term(
                term_lower, expansions_db, project_key, max_expansions
            )

            if expanded:
                expansion_map[term] = expanded
                all_terms.update(expanded)

        self.logger.info(
            f"Query expansion: '{query}' → {len(all_terms)} total terms "
            f"({len(all_terms) - len(query_terms)} added)"
        )

        if expansion_map:
            self.logger.debug(f"Expansions: {expansion_map}")

        return all_terms, expansion_map

    def _tokenize(self, query: str) -> List[str]:
        """Tokenize query into words.

        Args:
            query: Query string

        Returns:
            List of words
        """
        # Extract words (alphanumeric and hyphens/underscores)
        words = re.findall(r"\b[\w-]+\b", query.lower())
        return [w for w in words if len(w) >= 2]  # Filter very short words

    def _load_expansions(
        self, project_key: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Load query expansions from database with caching.

        Args:
            project_key: Optional project filter

        Returns:
            Dict mapping original_term -> [expansion_dicts]
        """
        # Check cache (5 minute TTL)
        if (
            self._cache_time
            and (datetime.now() - self._cache_time).total_seconds() < 300
        ):
            if self._expansion_cache:
                return self._expansion_cache

        try:
            from src.utils.database import session_scope
            from src.models.search_feedback import QueryExpansion

            expansions = {}

            with session_scope() as session:
                # Load active expansions
                # Filter by project if provided, otherwise get global expansions
                query = session.query(QueryExpansion).filter(
                    QueryExpansion.is_active == True
                )

                if project_key:
                    # Get both project-specific and global (project_key IS NULL) expansions
                    query = query.filter(
                        (QueryExpansion.project_key == project_key)
                        | (QueryExpansion.project_key.is_(None))
                    )
                else:
                    # Only global expansions
                    query = query.filter(QueryExpansion.project_key.is_(None))

                for exp in query.all():
                    original = exp.original_term.lower()
                    if original not in expansions:
                        expansions[original] = []

                    expansions[original].append(
                        {
                            "term": exp.expanded_term.lower(),
                            "type": exp.expansion_type,
                            "confidence": exp.confidence_score,
                            "success_rate": (
                                (exp.success_count / exp.usage_count)
                                if exp.usage_count > 0
                                else 0.5
                            ),
                        }
                    )

            self._expansion_cache = expansions
            self._cache_time = datetime.now()

            self.logger.info(
                f"Loaded {len(expansions)} query expansion rules from database"
            )

            return expansions

        except Exception as e:
            self.logger.error(f"Error loading query expansions: {e}")
            # Return empty dict on error
            return {}

    def _get_expansions_for_term(
        self,
        term: str,
        expansions_db: Dict[str, List[Dict[str, Any]]],
        project_key: Optional[str],
        max_expansions: int,
    ) -> List[str]:
        """Get expansions for a single term.

        Args:
            term: Term to expand
            expansions_db: Preloaded expansions from database
            project_key: Optional project context
            max_expansions: Maximum expansions to return

        Returns:
            List of expanded terms
        """
        expanded = []

        # 1. Database expansions (synonyms, acronyms, learned)
        if term in expansions_db:
            # Sort by confidence * success_rate
            db_expansions = sorted(
                expansions_db[term],
                key=lambda x: x["confidence"] * x["success_rate"],
                reverse=True,
            )

            # Add top expansions
            for exp in db_expansions[:max_expansions]:
                expanded.append(exp["term"])

        # 2. Morphological variations (plural/singular)
        if not expanded or len(expanded) < max_expansions:
            morphological = self._get_morphological_variations(term)
            for var in morphological:
                if var not in expanded and len(expanded) < max_expansions:
                    expanded.append(var)

        return expanded[:max_expansions]

    def _get_morphological_variations(self, term: str) -> List[str]:
        """Get plural/singular variations of a term.

        Args:
            term: Original term

        Returns:
            List of morphological variations
        """
        variations = []

        # Simple plural/singular rules
        if term.endswith("s") and len(term) > 3:
            # Might be plural, try singular
            singular = term[:-1]
            variations.append(singular)

            # Handle -ies -> -y
            if term.endswith("ies"):
                singular_y = term[:-3] + "y"
                variations.append(singular_y)

        elif not term.endswith("s"):
            # Might be singular, try plural
            # Basic -s plural
            variations.append(term + "s")

            # -y -> -ies plural
            if term.endswith("y") and len(term) > 2:
                plural_ies = term[:-1] + "ies"
                variations.append(plural_ies)

        return variations

    async def record_expansion_usage(
        self, original_term: str, expanded_term: str, was_helpful: Optional[bool] = None
    ):
        """Record usage of a query expansion for learning.

        Args:
            original_term: Original term
            expanded_term: Expanded term that was used
            was_helpful: Whether the expansion led to good results (from feedback)
        """
        try:
            from src.utils.database import session_scope
            from src.models.search_feedback import QueryExpansion

            with session_scope() as session:
                # Find or create expansion
                expansion = (
                    session.query(QueryExpansion)
                    .filter(
                        QueryExpansion.original_term == original_term.lower(),
                        QueryExpansion.expanded_term == expanded_term.lower(),
                    )
                    .first()
                )

                if expansion:
                    # Update usage stats
                    expansion.usage_count += 1
                    if was_helpful is True:
                        expansion.success_count += 1

                    session.commit()

                    self.logger.debug(
                        f"Recorded expansion usage: '{original_term}' -> '{expanded_term}' "
                        f"(success_rate: {expansion.success_count}/{expansion.usage_count})"
                    )

        except Exception as e:
            self.logger.error(f"Error recording expansion usage: {e}")

    async def learn_expansion_from_feedback(
        self, query: str, results: List[Any], was_helpful: bool
    ):
        """Learn new query expansions from user feedback.

        Args:
            query: Original query
            results: Search results that were returned
            was_helpful: Whether user gave positive feedback
        """
        if not was_helpful:
            # Only learn from positive feedback
            return

        try:
            # Extract terms that appear in results but not in query
            query_terms = set(self._tokenize(query))

            # Get terms from result titles/content
            result_terms = set()
            for result in results[:10]:  # Top 10 results
                result_text = f"{result.title} {result.content}"
                result_terms.update(self._tokenize(result_text))

            # Find terms in results but not in query (potential new expansions)
            candidate_expansions = result_terms - query_terms

            # For each query term, find related result terms
            from src.utils.database import session_scope
            from src.models.search_feedback import QueryExpansion

            with session_scope() as session:
                for query_term in query_terms:
                    # Find semantically related candidates
                    # (In a more advanced version, use embedding similarity)
                    related = self._find_related_terms(query_term, candidate_expansions)

                    for related_term in related[:3]:  # Limit to 3 per term
                        # Check if expansion already exists
                        existing = (
                            session.query(QueryExpansion)
                            .filter(
                                QueryExpansion.original_term == query_term.lower(),
                                QueryExpansion.expanded_term == related_term.lower(),
                            )
                            .first()
                        )

                        if not existing:
                            # Create new learned expansion with low initial confidence
                            new_expansion = QueryExpansion(
                                original_term=query_term.lower(),
                                expanded_term=related_term.lower(),
                                expansion_type="learned",
                                confidence_score=0.3,  # Low initial confidence
                                usage_count=0,
                                success_count=0,
                                is_active=True,
                            )
                            session.add(new_expansion)

                            self.logger.info(
                                f"Learned new expansion: '{query_term}' -> '{related_term}'"
                            )

                session.commit()

        except Exception as e:
            self.logger.error(f"Error learning expansion from feedback: {e}")

    def _find_related_terms(self, query_term: str, candidates: Set[str]) -> List[str]:
        """Find terms related to query term from candidates.

        Args:
            query_term: Original term
            candidates: Candidate expansion terms

        Returns:
            List of related terms
        """
        # Simple heuristic: find terms that share prefix/suffix or are substrings
        related = []

        query_lower = query_term.lower()

        for candidate in candidates:
            candidate_lower = candidate.lower()

            # Skip if too similar or same
            if candidate_lower == query_lower:
                continue

            # Check for substring relationship
            if query_lower in candidate_lower or candidate_lower in query_lower:
                related.append(candidate)
                continue

            # Check for shared prefix (3+ chars)
            if len(query_lower) >= 3 and len(candidate_lower) >= 3:
                if query_lower[:3] == candidate_lower[:3]:
                    related.append(candidate)

        return related[:5]  # Limit to 5
