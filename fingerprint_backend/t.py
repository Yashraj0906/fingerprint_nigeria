import base64

with open("test.jpeg", "rb") as f:
    encoded = base64.b64encode(f.read()).decode()

with open("output.txt", "w") as f:
    f.write(encoded)

print("Saved to output.txt ✅")