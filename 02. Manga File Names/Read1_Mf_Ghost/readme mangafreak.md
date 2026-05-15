Here's how the script works for mangafreak:

Install dependency:

```bash
pip install requests beautifulsoup4 tqdm
```

Download a single chapter:

```python
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1
```

Download a range:

```python
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters 1-10
```

Download everything:

```python
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters all

```

Since I couldn't inspect the live page, the script tries 10 different CSS selectors in order to find the images. If it prints "No images found", run with `--debug` first:

```python
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --debug
```

That dumps every `<img>` tag on the page. Paste the output here and I can add the exact selector.