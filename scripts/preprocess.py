"""Script to convert raw character scripts into JSONL dialogue dataset for fine-tuning.

This script processes all `.txt` files in the input directory, extracts user and assistant
dialogues based on speaker tags, and outputs a JSONL file suitable for LLM fine-tuning.
"""

import json
import os

# ================= CONFIGURATION =================
INPUT_DIR = "../data/raw"  # Directory containing all raw txt scripts
OUTPUT_FILE = "../data/raw/nene_finetune.jsonl"  # Output JSONL dataset file

# Strong system prompt for the assistant
SYSTEM_PROMPT = (
    "You are Ayachi Nene from 'The Witch's Banquet'. "
    "You are gentle and responsible, usually a library committee member, "
    "but secretly a witch. You are soft-spoken to people you like, "
    "and sometimes shy or tsundere. Please respond in Nene's tone."
)

# Recognized speaker names
USER_NAMES = ["Hiiragi Fumi", "Hiroshi Hiiragi", "Protagonist"]
ASSISTANT_NAMES = ["Nene", "Ayachi Nene", "綾地寧々"]
# ================================================


def process_scripts():
    """Process all txt scripts in INPUT_DIR and save them as a JSONL dataset."""
    dataset = []
    total_files = 0

    if not os.path.exists(INPUT_DIR):
        print(f"Please create {INPUT_DIR} and put your txt script files there.")
        return

    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(INPUT_DIR, filename)
        total_files += 1
        print(f"Processing file: {filename} ...")

        current_speaker = None
        last_user_text = None

        lines = []

        # Try common encodings to read the file
        for encoding in ["utf-8", "gb18030", "shift_jis"]:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    lines = f.readlines()
                print(f"  -> Successfully read with {encoding} encoding.")
                break
            except UnicodeDecodeError:
                continue

        if not lines:
            print(
                f"  -> [ERROR] Could not read {filename} with common encodings. "
                "Please check if the file is corrupted."
            )
            continue

        for line in lines:
            line = line.strip()

            if line.startswith(";["):
                parts = line.split("]", 1)
                if len(parts) < 2:
                    continue

                content = parts[1].strip()
                if not content:
                    continue

                # State machine logic
                if content in USER_NAMES or content in ASSISTANT_NAMES:
                    current_speaker = content

                elif content.startswith("「") and content.endswith("」"):
                    dialogue = content.strip("「」")

                    if current_speaker in USER_NAMES:
                        last_user_text = dialogue

                    elif current_speaker in ASSISTANT_NAMES:
                        if last_user_text:
                            dataset.append(
                                {
                                    "messages": [
                                        {"role": "system", "content": SYSTEM_PROMPT},
                                        {"role": "user", "content": last_user_text},
                                        {"role": "assistant", "content": dialogue},
                                    ]
                                }
                            )
                            last_user_text = None
                else:
                    current_speaker = None

    # Write the JSONL dataset
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(
        f"Extraction complete! Processed {total_files} files, "
        f"generated {len(dataset)} high-quality Nene dialogues."
    )


if __name__ == "__main__":
    process_scripts()
