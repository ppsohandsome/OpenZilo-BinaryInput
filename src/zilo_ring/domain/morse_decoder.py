from __future__ import annotations


DOWN_SINGLE = "single_press_rebound"
UP_SINGLE = "up_flick_rebound"
DOWN_DOUBLE = "double_press_rebound"

ACTION_TO_BIT = {
    DOWN_SINGLE: "0",
    UP_SINGLE: "1",
}

MORSE_BITS_TO_CHARACTER = {
    "01": "A",
    "1000": "B",
    "1010": "C",
    "100": "D",
    "0": "E",
    "0010": "F",
    "110": "G",
    "0000": "H",
    "00": "I",
    "0111": "J",
    "101": "K",
    "0100": "L",
    "11": "M",
    "10": "N",
    "111": "O",
    "0110": "P",
    "1101": "Q",
    "010": "R",
    "000": "S",
    "1": "T",
    "001": "U",
    "0001": "V",
    "011": "W",
    "1001": "X",
    "1011": "Y",
    "1100": "Z",
    "11111": "0",
    "01111": "1",
    "00111": "2",
    "00011": "3",
    "00001": "4",
    "00000": "5",
    "10000": "6",
    "11000": "7",
    "11100": "8",
    "11110": "9",
}


class MorseDecoder:
    """Translate the three existing gesture labels into Morse text."""

    def __init__(self) -> None:
        self.bits = ""
        self.text = ""
        self.message = "Waiting for an action"
        self.error = False

    @property
    def symbols(self) -> str:
        return self.bits.translate(str.maketrans({"0": "·", "1": "—"}))

    def feed(self, label: str) -> bool:
        bit = ACTION_TO_BIT.get(label)
        if bit is not None:
            if len(self.bits) >= 5:
                self.message = "Maximum Morse length is 5; undo or compile"
                self.error = True
                return False
            self.bits += bit
            self.message = f"Added {bit}"
            self.error = False
            return True

        if label != DOWN_DOUBLE:
            return False
        if not self.bits:
            self.message = "Nothing to compile"
            self.error = False
            return True

        character = MORSE_BITS_TO_CHARACTER.get(self.bits)
        if character is None:
            self.message = f"Unknown Morse sequence: {self.bits}"
            self.error = True
            return True

        source = self.bits
        self.text += character
        self.bits = ""
        self.message = f"Compiled {source} → {character}"
        self.error = False
        return True

    def undo_bit(self) -> None:
        if self.bits:
            self.bits = self.bits[:-1]
            self.message = "Removed the last bit"
        else:
            self.message = "No pending bit to remove"
        self.error = False

    def delete_character(self) -> None:
        if self.text:
            self.text = self.text[:-1]
            self.message = "Removed the last character"
        else:
            self.message = "No translated character to remove"
        self.error = False

    def clear(self) -> None:
        self.bits = ""
        self.text = ""
        self.message = "Cleared"
        self.error = False
