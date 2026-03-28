import os

def fix_generate_static():
    with open('generate_static.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Fix the regex syntax issue
    old_regex = r"return string.replace(/[.*+?^${{}}()|[\]\\]/g, '\\$&');"
    new_regex = r"return string.replace(/[.*+?^${{}}()|\[\]\\]/g, '\\\\$&');"
    content = content.replace(old_regex, new_regex)

    # 2. Remove the admin upload logic
    admin_logic = """
            // Admin Logic
            if(queryLower === 'upload') {{
                setTimeout(() => {{
                    const creds = prompt("ENTER ADMIN IDENTITY:");
                    if(creds === "Alvido") {{
                        alert("ACCESS GRANTED. (Static version - redirecting to registry)");
                        document.getElementById('feature-registry').style.display = 'block';
                    }}
                }}, 500);
            }}"""
    content = content.replace(admin_logic, "")

    with open('generate_static.py', 'w', encoding='utf-8') as f:
        f.write(content)

def fix_templates_index():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Remove admin logic from index.html
    admin_logic = """
            // ADMIN LOGIN TRIGGER
            if(q.toLowerCase() === 'upload') {
                searchTimeout = setTimeout(() => {
                    const creds = prompt("ENTER ADMIN IDENTITY:");
                    if(creds === "Alvido") {
                        alert("ACCESS GRANTED. OPENING UPLOAD PANEL...");
                    } else {
                        alert("ACCESS DENIED.");
                    }
                }, 100);
                return;
            }"""
    content = content.replace(admin_logic, "")
    
    # Also remove it from the list
    content = content.replace("<li><span>Admin:</span> Secure Upload Enabled</li>", "")

    # For the shortcuts, C+O+2 is working fine, but wait, the prompt said:
    # "neither co2 is working" 
    # Why is CO2 not working? Look at `keys['c'] && keys['o'] && keys['2']`. Event listener might be broken from the regex fail above it!
    # In index.html, it didn't fail. But let's check index.html's keys C+O+2 logic.

    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_generate_static()
    fix_templates_index()
    print("Patched!")