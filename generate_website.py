import os
import shutil
import glob
import markdown
import re
import sys
import argparse
import pandas as pd

# Add src to path to import generate_results_report
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from visualization.generate_results_report import generate_reports_from_dir

# Configuration
DOCS_DIR = 'docs'
IMGS_DIR = 'imgs'
CONTENT_FILE_MD = 'docs/web_content.md'
CONTENT_FILE_HTML = 'docs/web_content.html'
RESULTS_DIR = 'results_subsampled_8'
RESULTS_ROOT_DIR = 'results' # New root results dir for data maps
MODEL_COMPARISON_FILE = os.path.join(RESULTS_DIR, 'model_comparison.md')

# Ensure docs dir exists
os.makedirs(DOCS_DIR, exist_ok=True)

print(f"Generating website in {DOCS_DIR}...")

# 0. Generate results report
print("Generating result reports...")
generate_reports_from_dir(RESULTS_DIR, RESULTS_DIR)

# 1. Copy images to docs/imgs for self-contained deployment
DEST_IMGS = os.path.join(DOCS_DIR, 'imgs')
if os.path.exists(IMGS_DIR):
    os.makedirs(DEST_IMGS, exist_ok=True)

    # Copy without deleting DEST_IMGS so manually-added assets (e.g., bg_*.jpg) are preserved.
    try:
        shutil.copytree(IMGS_DIR, DEST_IMGS, dirs_exist_ok=True)
    except TypeError:
        # Python < 3.8 fallback: copy file-by-file
        for root, dirs, files in os.walk(IMGS_DIR):
            rel = os.path.relpath(root, IMGS_DIR)
            dest_root = os.path.join(DEST_IMGS, rel) if rel != "." else DEST_IMGS
            os.makedirs(dest_root, exist_ok=True)
            for fname in files:
                shutil.copy2(os.path.join(root, fname), os.path.join(dest_root, fname))

    print(f"Synced {IMGS_DIR} to {DEST_IMGS}")

# 2. Copy result data (images/visuals)
DEST_RESULTS = os.path.join(DOCS_DIR, 'results_data')
if os.path.exists(RESULTS_DIR):
    if os.path.exists(DEST_RESULTS):
        shutil.rmtree(DEST_RESULTS)
    # Copy results_subsampled_8 content
    shutil.copytree(RESULTS_DIR, DEST_RESULTS, ignore=shutil.ignore_patterns('*.zarr', '*.nc'))
    print(f"Copied {RESULTS_DIR} to {DEST_RESULTS} (excluding .zarr and .nc files)")

# 2.1 Copy results root data (data maps, etc) if available
# This merges 'results/' content into 'results_data/' alongside subsampled results
if os.path.exists(RESULTS_ROOT_DIR):
    print(f"Copying {RESULTS_ROOT_DIR} content to {DEST_RESULTS}...")
    for item in os.listdir(RESULTS_ROOT_DIR):
        s = os.path.join(RESULTS_ROOT_DIR, item)
        d = os.path.join(DEST_RESULTS, item)
        if os.path.isdir(s):
            # If dir exists in dest, merge? shutil.copytree dirs_exist_ok=True (py3.8+)
            # Or simplified: only copy files or non-existing dirs
            if not os.path.exists(d):
                shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    print(f"Merged {RESULTS_ROOT_DIR} into {DEST_RESULTS}")


SITE_TITLE = "ClimX: Extreme-aware climate model emulation"
SITE_SHORT_NAME = "ClimX"
GITHUB_REPO_URL = "https://github.com/IPL-UV/ClimX"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{site_title}</title>
    <link rel="stylesheet" href="style.css">
    <script src="bg.js" defer></script>
    <!-- MathJax for LaTeX support -->
    <script>
    MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']]
      }}
    }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script>
        function toggleMenu() {{
            var x = document.getElementById("mobile-menu");
            if (x.style.display === "block") {{
                x.style.display = "none";
            }} else {{
                x.style.display = "block";
            }}
        }}
    </script>
</head>
<body>
    <canvas id="bg-canvas" aria-hidden="true"></canvas>
    <header>
        <div class="container">
            <nav>
                <div class="logo">
                    <a href="index.html" style="color: white; text-decoration: none; display: flex; align-items: center;">
                        <img src="imgs/logo.png" alt="{site_short_name} logo" style="height: 40px; vertical-align: middle; margin-right: 10px;">
                        <strong>{site_short_name}</strong>
                    </a>
                </div>
                <div class="links desktop-links">
                    <a href="index.html">Home</a>
                    <a href="visualizations.html">Visualizations</a>
                    <div class="dropdown">
                        <button class="dropbtn" aria-haspopup="true">
                            <span style="display: inline-flex; align-items: center; gap: 0.4rem;">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" focusable="false" aria-hidden="true">
                                    <path d="M4 19a1 1 0 0 1-1-1V6a1 1 0 0 1 2 0v12h16a1 1 0 1 1 0 2H4Zm4-3a1 1 0 0 1-1-1V9a1 1 0 0 1 2 0v6a1 1 0 0 1-1 1Zm4 0a1 1 0 0 1-1-1V7a1 1 0 0 1 2 0v8a1 1 0 0 1-1 1Zm4 0a1 1 0 0 1-1-1V11a1 1 0 1 1 2 0v4a1 1 0 0 1-1 1Z"/>
                                </svg>
                                Baselines ▼
                            </span>
                        </button>
                        <div class="dropdown-content">
                            {baseline_links_html}
                        </div>
                    </div>
                </div>
                <div class="mobile-menu-icon" onclick="toggleMenu()">
                    &#9776;
                </div>
            </nav>
            <div id="mobile-menu" class="mobile-links" style="display: none;">
                <a href="index.html">Home</a>
                <a href="visualizations.html">Visualizations</a>
                <div class="mobile-divider">Baselines:</div>
                {baseline_links_html}
            </div>
        </div>
    </header>

    <main>
        {content}
    </main>

    <footer class="footer">
        <div class="container">
            <p>&copy; 2026 {site_short_name} organizers. Powered by <a href="{github_repo_url}">GitHub</a>.</p>
            <p class="small-muted" style="margin-top: 0.75rem;">
                Oscar Pellicer · Esther Rodrigo Bonet · Kai-Hendrik Cohrs · Maria Gonzalez · Nathan Mankovich · Gustau Camps-Valls
            </p>
        </div>
    </footer>
</body>
</html>
"""

def convert_md_to_html(md_content):
    # Fix image paths for the HTML context
    content = md_content
    
    # 1. Main images: "imgs/..." -> "imgs/..." (already correct relative to docs/)
    # But if the MD says "imgs/ghg.png", and we are in docs/, and we copied imgs to docs/imgs, it works.
    
    # 2. Result images: The result MDs generated by generate_results_report.py likely reference
    # "linear_monthly_visuals/..." or similar relative to the MD location.
    # We moved the data to "results_data/linear_monthly_visuals/...".
    
    # Also handle results root images (data maps) which might be referenced as "results/..." or similar
    content = content.replace('src="results/', 'src="results_data/')
    content = content.replace('](results/', '](results_data/')

    # Check for likely visual directories in results_data
    if os.path.exists(DEST_RESULTS):
        visual_dirs = [d for d in os.listdir(DEST_RESULTS) if os.path.isdir(os.path.join(DEST_RESULTS, d))]
        
        for vdir in visual_dirs:
            # Replace "vdir/" with "results_data/vdir/"
            # We look for " src="vdir/" or "](vdir/" or " vdir/"
            content = content.replace(f'src="{vdir}/', f'src="results_data/{vdir}/')
            content = content.replace(f']({vdir}/', f'](results_data/{vdir}/')
    
    # Convert to HTML
    html = markdown.markdown(content, extensions=['tables', 'fenced_code'])
    
    # Post-processing HTML to add classes to tables/images if needed
    html = html.replace('<table>', '<div class="table-wrapper"><table>')
    html = html.replace('</table>', '</table></div>')
    
    return html

def parse_model_comparison(file_path):
    """
    Parses the model comparison markdown to extract the ranking table or other summaries.
    Simple parsing assuming standard markdown table format.
    """
    if not os.path.exists(file_path):
        return None
    
    with open(file_path, 'r') as f:
        content = f.read()

    # Extract Ranking Table
    # Looks for "## Ranking" followed by table
    match = re.search(r'## Ranking\n\n.*?(\n\|.*\|\n(\n\|.*\|)+)', content, re.DOTALL)
    if match:
        ranking_table_md = match.group(1).strip()
        # Convert MD table to HTML using markdown lib
        ranking_html = markdown.markdown(ranking_table_md, extensions=['tables'])
        ranking_html = ranking_html.replace('<table>', '<table class="ranking-table">')
        return ranking_html
    return None

def main():
    # Find result files
    result_files = glob.glob(os.path.join(RESULTS_DIR, '*_results.md'))
    
    # Prepare Links for Nav
    baseline_links = []
    baseline_list_items = []
    
    # Helper to get model name
    def get_model_info(res_file):
        basename = os.path.basename(res_file)
        model_name = basename.replace('_results.md', '').replace('_', ' ').title()
        html_filename = basename.replace('.md', '.html')
        return model_name, html_filename

    # Sort files
    sorted_files = sorted(result_files)

    for res_file in sorted_files:
        model_name, html_filename = get_model_info(res_file)
        
        # Nav link
        baseline_links.append(f'<a href="{html_filename}">{model_name}</a>')
        
        # Index list item with code link
        # Infer code path
        code_path = f"{GITHUB_REPO_URL}/tree/main/src/models"
        if "Linear" in model_name:
            code_file = "linear_model.py"
            icon = "Linear"
        elif "Nn" in model_name or "Neural" in model_name:
            code_file = "nn_model.py"
            icon = "NN"
        elif "Gnn" in model_name:
            code_file = "gnn_model.py"  # baseline implementation
            icon = "GNN"
        elif "Climatology" in model_name:
            code_file = ""
            icon = "Climo"
        else:
            code_file = ""
            icon = "Model"
            
        full_code_url = f"{code_path}/{code_file}" if code_file else code_path
        
        list_item = f"""
        <li class="baseline-card">
            <a href="{html_filename}" class="baseline-link">
                <span class="icon">{icon}</span>
                <span class="name">{model_name}</span>
            </a>
            <a href="{full_code_url}" class="code-link" target="_blank">View Code</a>
        </li>
        """
        baseline_list_items.append(list_item)
    
    baseline_links_html = "\n".join(baseline_links)
    
    # Generate Result Pages
    for res_file in sorted_files:
        model_name, html_filename = get_model_info(res_file)
        
        with open(res_file, 'r') as f:
            res_md = f.read()
            
        res_html_content = convert_md_to_html(res_md)
        
        full_html = HTML_TEMPLATE.format(
            site_title=SITE_TITLE,
            site_short_name=SITE_SHORT_NAME,
            github_repo_url=GITHUB_REPO_URL,
            baseline_links_html=baseline_links_html,
            content=f'<div class="container prose">{res_html_content}</div>'
        )
        
        output_path = os.path.join(DOCS_DIR, html_filename)
        with open(output_path, 'w') as f:
            f.write(full_html)
        print(f"Generated {output_path}")

    # Generate Model Comparison Page
    if os.path.exists(MODEL_COMPARISON_FILE):
        with open(MODEL_COMPARISON_FILE, 'r') as f:
            comp_md = f.read()
        
        comp_html_content = convert_md_to_html(comp_md)
        comp_page_html = HTML_TEMPLATE.format(
            site_title=SITE_TITLE,
            site_short_name=SITE_SHORT_NAME,
            github_repo_url=GITHUB_REPO_URL,
            baseline_links_html=baseline_links_html,
            content=f'<div class="container prose">{comp_html_content}</div>'
        )
        with open(os.path.join(DOCS_DIR, 'model_comparison.html'), 'w') as f:
            f.write(comp_page_html)
        print(f"Generated {os.path.join(DOCS_DIR, 'model_comparison.html')}")
        
        # Add to Nav?
        # Maybe add "Comparison" to the baseline dropdown or main nav
        # For now, I'll add it to the dropdown as the first item
        baseline_links_html = f'<a href="model_comparison.html"><strong>Comparison Summary</strong></a>\n' + baseline_links_html


    # Process Visualizations Page
    visualizations_file = 'visualizations.md'
    if os.path.exists(visualizations_file):
        with open(visualizations_file, 'r') as f:
            viz_md = f.read()
        
        # Fix paths for visualisations.md specifically if needed
        # It uses src="results/..." which convert_md_to_html handles now
        viz_html_content = convert_md_to_html(viz_md)
        
        viz_page_html = HTML_TEMPLATE.format(
            site_title=SITE_TITLE,
            site_short_name=SITE_SHORT_NAME,
            github_repo_url=GITHUB_REPO_URL,
            baseline_links_html=baseline_links_html,
            content=f'<div class="container prose">{viz_html_content}</div>'
        )
        with open(os.path.join(DOCS_DIR, 'visualizations.html'), 'w') as f:
            f.write(viz_page_html)
        print(f"Generated {os.path.join(DOCS_DIR, 'visualizations.html')}")

    # Generate Main Page
    if os.path.exists(CONTENT_FILE_HTML):
        with open(CONTENT_FILE_HTML, 'r') as f:
            main_html_content = f.read()
        
        # Inject Baselines List
        baseline_list_html = "\n".join(baseline_list_items)
        main_html_content = re.sub(
            r'(<ul class="fancy-list">).*?(</ul>)', 
            f'\\1{baseline_list_html}\\2', 
            main_html_content, 
            flags=re.DOTALL
        )
        
        # Inject Ranking Table if available
        ranking_html = parse_model_comparison(MODEL_COMPARISON_FILE)
        if ranking_html:
            # We want to inject this into the main page, maybe under "Baselines & Results"
            # Look for <div class="baselines-list"> or similar
            # Insert before it
            insertion_point = '<div class="baselines-list">'
            ranking_section = f"""
            <div class="ranking-section">
                <h3>Current Leaderboard</h3>
                <p>Ranking based on best performance counts across all metrics.</p>
                {ranking_html}
                <div class="text-center" style="margin-top: 1rem;">
                    <a href="model_comparison.html" class="btn btn-primary">View Full Comparison</a>
                </div>
            </div>
            """
            main_html_content = main_html_content.replace(insertion_point, ranking_section + insertion_point)
        
        index_html = HTML_TEMPLATE.format(
            site_title=SITE_TITLE,
            site_short_name=SITE_SHORT_NAME,
            github_repo_url=GITHUB_REPO_URL,
            baseline_links_html=baseline_links_html,
            content=main_html_content
        )
        
        with open(os.path.join(DOCS_DIR, 'index.html'), 'w') as f:
            f.write(index_html)
        print(f"Generated {os.path.join(DOCS_DIR, 'index.html')}")

    else:
        print("Error: content html not found")

def serve():
    import http.server
    import socketserver
    
    PORT = 8000
    os.chdir(DOCS_DIR)
    
    Handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\nServing website at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()

    main()
    
    if args.serve:
        serve()
