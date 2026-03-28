import re

with open('README.md', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add Features
features_old = "- **🔄 Real-time Scraping**: Live data synchronization from Galgotias University announcements"
features_new = "- **🔄 Real-time Scraping**: Live data synchronization from Galgotias University announcements\n- **📄 Smart Context Descriptions**: 1-line PDF summary/preview right on the dashboard\n- **🏷️ Category Tagging**: Instant visual tags (e.g. Exam, Fees) appended to cards"
text = text.replace(features_old, features_new)

# 2. Add troubleshooting section
contrib_old = "## 🤝 Contributing"
contrib_new = "## 🔄 Version Management & Troubleshooting\n\nIf experimental features break your site, you can revert back to the last known fully stable version (where short contexts, tags, and PDFs all worked perfectly).\n\n**The Stable Version (Commit: e1df46c)**\n- [Direct Link to Source Code for Version e1df46c](https://github.com/anacondy/3-GAL/tree/e1df46c)\n\n### How to manually restore to this stable version:\nIf you mess up your local files or site structure, run these exact commands in your terminal:\n`ash\n# 1. Force your local codebase back to the stable commit\ngit reset --hard e1df46c\n\n# 2. Force push this restored version back to GitHub to fix the live site\ngit push -f origin main\n`\n\n## 🤝 Contributing"
text = text.replace(contrib_old, contrib_new)

# 3. Add screenshot placeholder
demo_old = "**[View Live Site](https://anacondy.github.io/3-GAL/)** - Automatically updated daily with fresh announcements."
demo_new = "**[View Live Site](https://anacondy.github.io/3-GAL/)** - Automatically updated daily with fresh announcements.\n\n> *[📸 Make sure to upload a new Screenshot/GIF here showing the newly updated UI with Tags and Context Descriptions!]*"
text = text.replace(demo_old, demo_new)

with open('README.md', 'w', encoding='utf-8') as f:
    f.write(text)
