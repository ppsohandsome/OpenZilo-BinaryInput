from zilo_ring.domain import DOWN_DOUBLE, DOWN_SINGLE, UP_SINGLE, MorseDecoder


def test_decodes_existing_gesture_labels_as_morse() -> None:
    decoder = MorseDecoder()

    decoder.feed(DOWN_SINGLE)
    decoder.feed(UP_SINGLE)
    decoder.feed(DOWN_DOUBLE)

    assert decoder.bits == ""
    assert decoder.text == "A"
    assert decoder.message == "Compiled 01 → A"


def test_invalid_sequence_is_retained_for_correction() -> None:
    decoder = MorseDecoder()

    for label in (UP_SINGLE, DOWN_SINGLE, UP_SINGLE, DOWN_SINGLE, UP_SINGLE):
        decoder.feed(label)
    decoder.feed(DOWN_DOUBLE)

    assert decoder.bits == "10101"
    assert decoder.text == ""
    assert decoder.error is True


def test_unknown_and_empty_compile_do_not_add_text() -> None:
    decoder = MorseDecoder()

    assert decoder.feed("gesture_negative_v2") is False
    assert decoder.feed(DOWN_DOUBLE) is True
    assert decoder.text == ""
    assert decoder.bits == ""
