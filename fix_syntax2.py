import os

def fix_generate_static():
    with open('generate_static.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # REMOVE ALL REGEX IN THE ESCAPEREGEXP FUNCTION! 
    # Use split and join for characters instead of regex brackets that conflict with Python!
    old_escape = r"""        function escapeRegExp(string) {{
            return string.replace(/[.*+?^${{}}()|\[\]\\]/g, '\\\\$&');
        }}"""
    
    new_escape = r"""        function escapeRegExp(string) {{
            const specials = [".", "*", "+", "?", "^", "$", "{", "}", "(", ")", "|", "[", "]", "\\"];
            let result = string;
            for (let i = 0; i < specials.length; i++) {{
                result = result.split(specials[i]).join("\\" + specials[i]);
            }}
            return result;
        }}"""
    content = content.replace(old_escape, new_escape)

    # I also need to make sure the previous regex replace didn't fail.
    # What was the original in generate_static before the last run?
    old_escape_fallback = r"""        function escapeRegExp(string) {{
            return string.replace(/[.*+?^${{}}()|[\]\\]/g, '\\$&');
        }}"""
    content = content.replace(old_escape_fallback, new_escape)

    with open('generate_static.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_generate_static()
    print("Patched!")