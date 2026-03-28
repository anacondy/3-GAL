# Advanced Search Highlighting (Future Implementation)

This document preserves the DOM-safe contextual search highlighting logic. It uses Regular Expressions (Regex) to dynamically wrap matched text in `<mark>` tags, styling them in the site's signature yellow accent color (`var(--text-accent)`).

## Why is this not deployed right now?
The current static site compiler (`generate_static.py`) uses **Python f-strings** (`f'''...'''`) to generate the entire HTML/JS file. Python f-strings use `{}` and `[]` brackets for variable interpolation. Unfortunately, JavaScript Regular Expressions *also* heavily rely on these exact same brackets to define capture groups and character classes. 

When Python tries to render the Regex, it misinterprets the JS brackets as Python variables, crashes, and outputs broken syntax. 

**To use this code in the future, the project needs a minor architecture restructure:**
Instead of `generate_static.py` returning one massive `f-string`, it should process the static HTML using **Jinja2** (the templating engine Flask already uses in `templates/index.html`). Jinja2 natively separates backend code from frontend markup, completely eliminating "bracket escaping" conflicts.

---

## The Code

If/When the static builder is restructured to use Jinja templates, or if this is broken out into a separate `search.js` file, here is the exact functioning logic to implement Contextual Yellow Highlighting safely:

```javascript
// 1. Store the original, unaltered HTML state of the cards on load
const allCards = document.querySelectorAll('.exam-card');
const cardsData = Array.from(allCards).map(card => {
    return {
        element: card,
        // We only save the inner content of the card-header. 
        // This prevents overwriting the `onclick` PDF trigger on the parent card.
        originalHTML: card.querySelector('.card-header').innerHTML,
        textContent: card.textContent.toLowerCase()
    };
});

// 2. Safely escape any special characters a user might type in the search bar
function escapeRegExp(string) {
    // Escapes special regex characters: . * + ? ^ $ { } ( ) | [ ] \
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 3. Wrap matched text in a highly visible yellow <mark> tag
function highlightMatch(html, query) {
    if (!query) return html;
    
    // Create a global, case-insensitive regex payload from the user's query
    const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
    
    // We split by HTML tags like <div class="..."> so we don't accidentally 
    // highlight and break the actual HTML structural definitions.
    return html.split(/(<[^>]*>)/).map(part => {
        if (part.startsWith('<')) return part; // Skip structural tags
        
        // Apply the highlight injection strictly to text nodes
        return part.replace(regex, '<mark style="background-color: var(--text-accent); color: #000; padding: 0 2px; border-radius: 2px;">$1</mark>');
    }).join('');
}

// 4. Attach event listener to the search input
document.getElementById('search-input').addEventListener('input', function(e) {
    const query = e.target.value.trim();
    const queryLower = query.toLowerCase();
    
    const resultsContainer = document.getElementById('results-list');
    const matches = [];
    const nonMatches = [];

    // Loop over our stored card elements
    cardsData.forEach(data => {
        const header = data.element.querySelector('.card-header');
        
        if (query === '') {
            // Restore original HTML & visibility if search is cleared
            data.element.style.display = 'block';
            header.innerHTML = data.originalHTML;
            matches.push(data.element);
        } else {
            if (data.textContent.includes(queryLower)) {
                // If it matches the search, display it and inject the <mark> tags
                data.element.style.display = 'block';
                header.innerHTML = highlightMatch(data.originalHTML, query);
                matches.push(data.element);
            } else {
                // Hide non-matches, restore their HTML so they are clean if query changes
                data.element.style.display = 'none';
                header.innerHTML = data.originalHTML;
                nonMatches.push(data.element);
            }
        }
    });

    // 5. DOM Reordering
    // Only re-append matches to the top of the container while actively searching
    if (query !== '') {
        matches.forEach(m => resultsContainer.appendChild(m));
        nonMatches.forEach(m => resultsContainer.appendChild(m));
    } else {
        // If search is cleared, sort them back to their original timeline order
        matches.sort((a,b) => Array.from(allCards).indexOf(a) - Array.from(allCards).indexOf(b));
        matches.forEach(m => resultsContainer.appendChild(m));
    }
});
```