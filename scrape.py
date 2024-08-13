import requests
import os
from bs4 import BeautifulSoup, element
import json
from collections import Counter
import json
import os

email = 'laura@aishore.ai'

def s1_html(url):
    """
    Function to access the html using the edgar header
    Input: S-1 form url 
    Ouput: html string
    """
    headers = {'User-Agent': f'Aishore {email}'}
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        print(f"Status Code: {res.status_code}")
        print("HTML Content:")
        print(res.text)
    except requests.RequestException as e:
        print(f"An error occurred: {e}")

####### division of form by the table of contents #######
def find_toc_lines(soup):
    """
    Searches for the html containing the table of contents line
    Limited usage by how S-1 Forms format the table of contents
    Input: Soup HTML
    Output: List of lines with the words table of contents
    """
    toc_lines = []
    keywords = {'Table of Contents', 'TABLE OF CONTENTS', 'table of contents'}
    for element in soup.find_all(string=lambda text: text and any(keyword in text for keyword in keywords)):
        parent = element.find_parent()
        toc_lines.append(parent)
    return toc_lines

def identify_unique_toc(toc_lines):
    """
    Searches for the unique line among the list 
    The S-1 HTML is generally formatted such that each page has a link back to the table of contents
    Ignores those repeated lines and searches for the html line that points to the page with the table of contents
    Input: list of html string
    Output: single string of html
    """
    line_counter = Counter(map(str, toc_lines))
    unique_lines = [BeautifulSoup(line, 'html.parser').find() for line, count in line_counter.items() if count == 1]
    return unique_lines[0] if unique_lines else None

def extract_section_ids(soup, unique_toc_html):
    """
    Extract the section-ids pointing to each chapter in the html
    Searches for the page (center div container) that containes the unique toc html
    Then extracts all the href names
    Input: Soup HTML, String HTML line that points to the table of contents
    Output: List of string section_ids
    """
    toc_container = None
    toc_line_html = str(unique_toc_html)
    for element in soup.find_all(True): 
        if (str(element) == toc_line_html): 
            while element.name != 'div':
                element = element.parent
            toc_container = element
            break
    if not toc_container:
        raise ValueError("TOC container not found")    
    section_ids = []
    for a_tag in toc_container.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith('#'):
            section_ids.append(href[1:])  # Remove the '#' at the beginning
    return section_ids

def split_html_into_sections(soup, section_ids):
    """
    Splits the html into chapters, as defined by the section_ids retrieved from the toc
    Generally splits by pages (center div containers)
    However, if there is more than one chapter in a page, it artificially separates the chapter into two pages
    The Pre-TOC html is also included as the first chapter
    Input: Soup HTML
    Output: List of chapters, of which each chapter is a string of all the html in that chapter
    """
    sections = []
    current_section = []
    section_index = 0
    for center_tag in soup.find_all('center'):
        div_tag = center_tag.find('div')
        if not div_tag: 
            continue
        section_names = [a_tag['name'] for a_tag in div_tag.find_all('a', {'name': True}) if a_tag['name'] in section_ids]
        if section_names:
            if current_section:
                sections.append(' '.join(str(tag) for tag in current_section))
                current_section = []
            next_section = []
            while len(section_names) > 1:
                next_section = []
                in_next_section = False
                current_section = ["<center><div>"]
                for tag in div_tag.contents:
                    if not in_next_section:
                        current_section.append(tag)
                        if isinstance(tag.find('a'), element.Tag) and tag.find('a').get('name') == section_names[1]:
                            current_section = current_section[:-1]
                            current_section.append("</div></center>")
                            sections.append(' '.join(str(t) for t in current_section))
                            current_section = ["<center><div>"]
                            section_names = section_names[1:]
                            in_next_section = True
                            next_section.append(tag)
                    else:
                        next_section.append(tag)
                div_tag.contents = next_section
            if next_section: 
                next_section.append("</div></center>")
                current_section.append(' '.join(str(tag) for tag in next_section))
            else: 
                current_section.append(str(center_tag)) 
            section_index += 1
        else:
            current_section.append(str(center_tag))
    if current_section:
        sections.append(''.join(str(tag) for tag in current_section))
    return sections

def extract_text_and_tables(html_content):
    """
    Extracts all existing text in the HTML (removes the html code)
    Takes note if a table exists, then add markings to point to the table
    Input: HTML String block
    Output: String of the text and list/array with table information
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = ""
    tables = []
    table_counter = 0
    def process_table(table):
        nonlocal table_counter
        table_data = []
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            table_data.append(row_data)
        table_pointer = f"[TABLE_{table_counter}]"
        table_counter += 1
        tables.append(table_data)
        return table_pointer
    for element in soup.descendants:
        if isinstance(element, str):
            text += element.strip() + " "
        elif element.name == "table":
            table_pointer = process_table(element)
            text += f" {table_pointer} "
        elif element.name in ["p", "div"]:
            text += "\n"
    text = ' '.join(text.split())
    return text, tables
    
def word_count(text):
    """Finds the number of non-html text in html tags by space"""
    return len(text.split())

def chunk(soup, section_ids, token_size):
    """
    Function chunks S-1 form HTML to with maximal token sizes per chunk
    There exists roughly 1.5 tokens per word -- 128,000 token context window = ~85,000 words
    To be conservative, do 1.6 tokens per word
    Note a page on the form may have around 650-850 words

    Chunks look at html by chapter (by toc section_ids), section (by <b> tags or <table> tags)
    Optimally, though not coded, if there are sections between bolds that are just giant, then divide by paragraphs
    Given a large enough token size (several pages worth), this should never be the case

    Note that this function only functions properly given the entire soup and section_ids, 
    otherwise the key value pairings are off by one section_id
    This is because the first dict entry is hard-coded to be pre-section

    Input: Soup HTML, list of all section_ids, token-size, according to model specs
    Output: Dictionary matching section_id keys to list of chunks values
    """
    max_text_size = token_size//1.6
    sections_html = split_html_into_sections(soup, section_ids)
    chunk_dict = {}
    for section_index, section_html in enumerate(sections_html):
        section_soup = BeautifulSoup(section_html, 'html.parser')
        section_chunks = []
        current_chunk = []
        current_chunk_words = 0  
        for div in section_soup.find_all('div'):
            for tag in div.find_all(recursive=False):
                tag_str = str(tag)
                tag_text = tag.get_text()
                tag_words = word_count(tag_text)
                is_new_section = tag.name == 'b' or tag.find('b')
                is_table = tag.name == 'table'
                is_new_chapter = (tag.find('a', {'name': section_ids[section_index-1]}) is not None) if section_index>=1 else False
                if is_new_section or is_table or is_new_chapter:
                    if current_chunk:
                        section_chunks.append(current_chunk)
                    current_chunk = [tag_str]
                    current_chunk_words = tag_words
                else:
                    if current_chunk_words + tag_words <= max_text_size:
                        current_chunk.append(tag_str)
                        current_chunk_words += tag_words
                    else:
                        section_chunks.append(current_chunk)
                        current_chunk = [tag_str]
                        current_chunk_words = tag_words
            if current_chunk:
                section_chunks.append(current_chunk)
        curr_chapter_chunks = []
        current_chunk = []
        current_chunk_words = 0
        for chunk in section_chunks:
            chunk_words = word_count(' '.join(chunk))
            if current_chunk_words + chunk_words <= max_text_size:
                current_chunk.extend(chunk)
                current_chunk_words += chunk_words
            else:
                curr_chapter_chunks.append(current_chunk)
                current_chunk = chunk
                current_chunk_words = chunk_words
        if current_chunk:
            curr_chapter_chunks.append(current_chunk)
        dict_key = section_ids[section_index-1] if (section_index-1>=0) else 'pre-section' 
        chunk_dict[dict_key] = [''.join(chunk) for chunk in curr_chapter_chunks]
    return chunk_dict

def split_by_toc(url, save_dir, token_size = 800):
    """
    Given the URL of an S-1 HTML form, saves the text and table data in a JSON file, separated by TOC
    Input: The URL of the S-1 HTML form, directory name to save JSON file, token-size int
    Output: Saved filename, JSON file in format {section-id: {section_name: __, chunks: ['section chunk', ...]}, ...}
    """
    headers = {'User-Agent': f'Aishore {email}'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        toc_lines = find_toc_lines(soup)
        unique_toc_line = identify_unique_toc(toc_lines)
        section_ids = extract_section_ids(soup, unique_toc_line)
        os.makedirs(save_dir, exist_ok=True)
        chunked = chunk(soup, section_ids, token_size)
        file = {}
        filename = url.split('/')[-1].replace('.xml', '')
        for section_id, chunks in chunked.items():
            section_name = soup.find('a', attrs={'name': section_id}).find_parent().get_text(strip=True) if section_id != 'pre-section' else 'pre-section'
            file[section_id] = {
                "section_name": section_name,
                "chunks": []
            }
            for chunk_html in chunks:
                text, tables = extract_text_and_tables(chunk_html)
                chunk_data = {
                    "text": text,
                    "tables": tables
                }
                file[section_id]["chunks"].append(chunk_data)            
        file_path = os.path.join(save_dir, f"{filename}_chunk.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(file, f, ensure_ascii=True, indent=4)
        print(f"file saved to {file_path}")
        return save_dir
    except requests.RequestException as e:
        print(f"An error occurred while fetching the URL: {e}")
        return None
####### END division of form by the table of contents ######

####### DOWNLOAD FULL FORM #######
def extract_text_with_references(soup):
    """
    The original extraction function
    Extracts all existing text in the HTML (removes the html code)
    Takes note if a table exists, then add markings to point to the table
    Input: Soup HTML
    Output: Dictionary with text and tables keys
    """
    text_data = {
        "text": "",
        "tables": []
    }
    table_counter = 0
    def process_table(table):
        nonlocal table_counter
        table_data = []
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            table_data.append(row_data)
        table_pointer = f"[TABLE_{table_counter}]"
        table_counter += 1
        text_data["tables"].append(table_data)
        return table_pointer
    for element in soup.descendants:
        if isinstance(element, str):
            text_data["text"] += element.strip() + " "
        elif element.name == "table":
            table_pointer = process_table(element)
            text_data["text"] += f" {table_pointer} "
        elif element.name in ["p", "div"]:
            text_data["text"] += "\n"
    text_data["text"] = ' '.join(text_data["text"].split())
    return text_data

def s1_xml_download(url, save_dir):
    """
    Given the URL of an S-1 HTML form, saves the text and table data in a JSON file
    Input: The URL of the S-1 HTML form, directory name to save JSON file
    Output: Saved filename, JSON file in format {text: ... , tables: ...}
    """
    headers = {'User-Agent': f'Aishore {email}'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        cleaned_text = extract_text_with_references(soup)
        filename = url.split('/')[-1].replace('.xml', '')
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, f"{filename}_full.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            # json.dump({'text': cleaned_text, 'tokens': tokens}, f, ensure_ascii=False, indent=4)
            json.dump(cleaned_text, f, ensure_ascii=True, indent=4)
        print(f"File downloaded and saved to: {file_path}")
        return file_path
    except requests.RequestException as e:
        print(f"An error occurred while fetching the URL: {e}")
        return None
####### END DOWNLOAD FULL FORM #######

url = "https://www.sec.gov/Archives/edgar/data/1639825/000119312519230923/d738839ds1.htm"
save_directory = "sec_edgar_filings"
s1_xml_download(url, save_directory)
split_by_toc(url, save_directory)


prmpt="""The above is a section of an s-1 pre-IPO form. 
I am a financial analyst providing recommendations about this IPO company. 
I want to write an investment memo (2 to 3 pages) with the following sections: 
(1) High level introduction, quality of the business (operations, revenue breakdown, cost breakdown), growth perspective, market and macro background, and risks. 
The last 2 sections can use external sources. 
Please summarize the section with any information necessary to write this investment memo. 
Please make sure to provide numbers on the revenue breakdown and cost breakdown sections."""