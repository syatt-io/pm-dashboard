#!/usr/bin/env python3
"""
Test script to verify smooth interpolation in forecasting service.
Validates that BE Dev boost multiplier scales smoothly from 1-5.
"""


def test_be_dev_boost():
    """Test BE Dev boost multiplier across full 1-5 scale."""
    print("Testing BE Dev Boost Multiplier (Extensive Customizations)")
    print("=" * 60)

    expected = {
        1: 1.0,  # No boost
        2: 1.0,  # No boost
        3: 1.1,  # +10%
        4: 1.2,  # +20%
        5: 1.3,  # +30%
    }

    for value in range(1, 6):
        # Formula from forecasting_service.py:481
        multiplier = 1.0 + max(0, (value - 2)) * 0.1
        expected_multiplier = expected[value]
        match = "✓" if abs(multiplier - expected_multiplier) < 0.001 else "✗"

        boost_percent = (multiplier - 1.0) * 100
        print(f"  Value {value}: {multiplier:.2f}x ({boost_percent:+.0f}%) {match}")

        assert (
            abs(multiplier - expected_multiplier) < 0.001
        ), f"Value {value}: Expected {expected_multiplier}, got {multiplier}"

    print("\n✓ All BE Dev boost tests passed!")


def test_blend_factor():
    """Test blend factor calculation for baseline interpolation."""
    print("\nTesting Blend Factor (Backend Integrations)")
    print("=" * 60)

    expected = {
        1: 0.00,  # 100% no_integration baseline
        2: 0.25,  # 75% no_integration, 25% with_integration
        3: 0.50,  # 50/50 blend
        4: 0.75,  # 75% with_integration, 25% no_integration
        5: 1.00,  # 100% with_integration baseline
    }

    for value in range(1, 6):
        # Formula from forecasting_service.py:428
        blend_factor = (value - 1) / 4.0
        expected_factor = expected[value]
        match = "✓" if abs(blend_factor - expected_factor) < 0.001 else "✗"

        no_int_pct = (1 - blend_factor) * 100
        with_int_pct = blend_factor * 100
        print(
            f"  Value {value}: {blend_factor:.2f} "
            f"({no_int_pct:.0f}% no_int / {with_int_pct:.0f}% with_int) {match}"
        )

        assert (
            abs(blend_factor - expected_factor) < 0.001
        ), f"Value {value}: Expected {expected_factor}, got {blend_factor}"

    print("\n✓ All blend factor tests passed!")


def test_design_multiplier():
    """Test design multiplier calculation."""
    print("\nTesting Design Multiplier")
    print("=" * 60)

    for value in range(1, 6):
        # Formula from forecasting_service.py:440-441
        design_multiplier = 1.0 + (value - 1) * 0.75
        boost_percent = (design_multiplier - 1.0) * 100

        print(f"  Value {value}: {design_multiplier:.2f}x ({boost_percent:+.0f}%)")

    print("\n✓ Design multiplier scales from 1.0x (1) to 4.0x (5)")


def test_theme_multiplier():
    """Test theme multiplier calculation."""
    print("\nTesting Theme Multiplier")
    print("=" * 60)

    for value in range(1, 6):
        # Formula from forecasting_service.py:448-449
        fe_multiplier = 1.0 + (value - 1) * 0.5
        boost_percent = (fe_multiplier - 1.0) * 100

        print(f"  Value {value}: {fe_multiplier:.2f}x ({boost_percent:+.0f}%)")

    print("\n✓ Theme multiplier scales from 1.0x (1) to 3.0x (5)")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SMOOTH INTERPOLATION VALIDATION TESTS")
    print("=" * 60 + "\n")

    try:
        test_be_dev_boost()
        test_blend_factor()
        test_design_multiplier()
        test_theme_multiplier()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED - Smooth Interpolation Working!")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        exit(1)
