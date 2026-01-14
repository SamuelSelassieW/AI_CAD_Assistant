from pathlib import Path

base = Path(__file__).parent
p = base / "generated_models" / "plain_test.txt"
p.write_text("write ok")
print("wrote:", p)