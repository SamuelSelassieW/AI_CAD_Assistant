from pathlib import Path

base_dir = Path("generated_models")
base_dir.mkdir(parents=True, exist_ok=True)  # 🔥 creates folder safely

p = base_dir / "plain_test.txt"
p.write_text("write ok")

print("File written successfully!")
