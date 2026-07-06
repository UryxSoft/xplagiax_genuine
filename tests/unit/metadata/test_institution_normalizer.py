from app.infrastructure.metadata.institution_normalizer import InstitutionNormalizer


def test_exact_gazetteer_match_is_returned_as_is() -> None:
    normalizer = InstitutionNormalizer()
    assert normalizer.normalize("Universidad Nacional de Ingenieria") == "Universidad Nacional de Ingenieria"


def test_fuzzy_variant_maps_to_canonical_name() -> None:
    normalizer = InstitutionNormalizer()
    assert normalizer.normalize("UNIVERSIDAD NACIONAL DE INGENIERIA") == "Universidad Nacional de Ingenieria"


def test_abbreviation_is_expanded_before_matching() -> None:
    normalizer = InstitutionNormalizer()
    result = normalizer.normalize("Univ. Nacional de Ingenieria")
    assert result == "Universidad Nacional de Ingenieria"


def test_unknown_institution_returns_cleaned_text_not_none() -> None:
    normalizer = InstitutionNormalizer()
    result = normalizer.normalize("  Instituto Tecnologico Regional del Sur  ")
    assert result == "Instituto Tecnologico Regional del Sur"


def test_none_input_returns_none() -> None:
    normalizer = InstitutionNormalizer()
    assert normalizer.normalize(None) is None


def test_empty_string_returns_none() -> None:
    normalizer = InstitutionNormalizer()
    assert normalizer.normalize("   ") is None


def test_custom_gazetteer_is_respected() -> None:
    normalizer = InstitutionNormalizer(gazetteer=("Mi Universidad Personalizada",))
    assert normalizer.normalize("MI UNIVERSIDAD PERSONALIZADA") == "Mi Universidad Personalizada"
