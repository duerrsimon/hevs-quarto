import glob
import os
import asyncio
from playwright.async_api import async_playwright


notebooks = glob.glob("*/*.ipynb")


async def html_to_pdf(html_path, pdf_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{os.path.abspath(html_path)}")
        await page.pdf(path=pdf_path, format="A4", print_background=True)
        await browser.close()


for nb in notebooks:
    html_path = nb.replace(".ipynb", ".html")
    pdf_path = nb.replace(".ipynb", ".pdf")

    print(f"Rendering {nb} → HTML...")
    ret = os.system(f"quarto render {nb} --to html")
    if ret != 0:
        print(f"  ⚠ quarto failed for {nb}, skipping")
        continue

    if not os.path.exists(html_path):
        print(f"  ⚠ Expected {html_path} not found, skipping")
        continue

    print(f"Converting {html_path} → PDF...")
    asyncio.run(html_to_pdf(html_path, pdf_path))
    print(f"  ✓ {pdf_path}")
