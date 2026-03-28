import re

def safe_patch():
    with open('generate_static.py', 'r', encoding='utf-8') as f:
        content = f.read()

    new_static_search = r"""        // Store all cards for search
        const allCards = document.querySelectorAll('.exam-card');
        const cardsData = Array.from(allCards).map(card => {
            return {
                element: card,
                // store original text node content but we can just use the DOM structure directly safely
                originalHTML: card.querySelector('.card-header').innerHTML,
                textContent: card.textContent.toLowerCase()
            };
        });

        function escapeRegExp(string) {
            return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }

        function highlightMatch(html, query) {
            if (!query) return html;
            const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
            return html.split(/(<[^>]*>)/).map(part => {
                if (part.startsWith('<')) return part;
                return part.replace(regex, '<mark style="background-color: var(--text-accent); color: #000; padding: 0 2px; border-radius: 2px;">$1</mark>');
            }).join('');
        }

        // Search functionality
        document.getElementById('search-input').addEventListener('input', function(e) {
            const query = e.target.value.trim();
            const queryLower = query.toLowerCase();
            
            const resultsContainer = document.getElementById('results-list');
            const matches = [];
            const nonMatches = [];

            cardsData.forEach(data => {
                const header = data.element.querySelector('.card-header');
                if (query === '') {
                    data.element.style.display = 'block';
                    header.innerHTML = data.originalHTML;
                    matches.push(data.element);
                } else {
                    if (data.textContent.includes(queryLower)) {
                        data.element.style.display = 'block';
                        header.innerHTML = highlightMatch(data.originalHTML, query);
                        matches.push(data.element);
                    } else {
                        data.element.style.display = 'none';
                        header.innerHTML = data.originalHTML;
                        nonMatches.push(data.element);
                    }
                }
            });

            if (query !== '') {
                matches.forEach(m => resultsContainer.appendChild(m));
                nonMatches.forEach(m => resultsContainer.appendChild(m));
            } else {
                matches.sort((a,b) => Array.from(allCards).indexOf(a) - Array.from(allCards).indexOf(b));
                matches.forEach(m => resultsContainer.appendChild(m));
            }
        });

        // Keyboard Shortcut for Search (Ctrl+K or /)
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement !== document.getElementById('search-input'))) {
                e.preventDefault();
                document.getElementById('search-input').focus();
            }
        });"""

    new_static_search_fstring = new_static_search.replace('{', '{{').replace('}', '}}')

    # Find the bounds
    start_tag = "        // Store all cards for search"
    end_tag = "        }});"
    
    start_idx = content.find(start_tag)
    end_idx = content.find(end_tag, start_idx) + len(end_tag)

    if start_idx != -1 and end_idx != -1:
        content = content[:start_idx] + new_static_search_fstring + content[end_idx:]
        with open('generate_static.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched generate_static.py successfully.")
    else:
        print("Failed to find bounds.")


    # index.html patch
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    if 'e.ctrlKey && e.key === \'k\'' not in html_content:
        old_shortcut_html = r"""            if(e.key === 'Escape') {
                closePdf();
                closeSummary();
            }
        });"""
        new_shortcut_html = r"""            if(e.key === 'Escape') {
                closePdf();
                closeSummary();
            }
            if((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement !== document.getElementById('search-input'))) {
                e.preventDefault();
                document.getElementById('search-input').focus();
            }
        });"""
        html_content = html_content.replace(old_shortcut_html, new_shortcut_html)

    if "function renderCards(data) {" in html_content:
        helper = r"""
        function escapeRegExp(string) {
            return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }

        function highlightMatch(html, query) {
            if (!query) return html;
            const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
            return html.split(/(<[^>]*>)/).map(part => {
                if (part.startsWith('<')) return part;
                return part.replace(regex, '<mark style="background-color: var(--text-accent); color: #000; padding: 0 2px; border-radius: 2px;">$1</mark>');
            }).join('');
        }

        function renderCards(data, query="") {"""
        
        html_content = html_content.replace("function renderCards(data) {", helper)
        html_content = html_content.replace("renderCards(data);", "renderCards(data, query);")

        old_category = r'categoryHtml = `<span class="card-category">${escapeHtml(item.category)}</span>`;'
        new_category = r'categoryHtml = `<span class="card-category">${highlightMatch(escapeHtml(item.category), query)}</span>`;'
        html_content = html_content.replace(old_category, new_category)
        
        old_title = r'<div class="card-title">${escapeHtml(item.title || \'\')}</div>'
        new_title = r'<div class="card-title">${highlightMatch(escapeHtml(item.title || \'\'), query)}</div>'
        html_content = html_content.replace(old_title, new_title)
        
        old_desc = r'${escapeHtml(item.desc || "Click to view full official notification document.")}</div>'
        new_desc = r'${highlightMatch(escapeHtml(item.desc || "Click to view full official notification document."), query)}</div>'
        html_content = html_content.replace(old_desc, new_desc)

        with open('templates/index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("Patched templates/index.html successfully.")

if __name__ == '__main__':
    safe_patch()