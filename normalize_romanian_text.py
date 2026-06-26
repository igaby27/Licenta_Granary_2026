import json
import re
import sys
import argparse
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
from num2words import num2words

# Nucleul pentru cifre romane acceptă acum și terminațiile feminine "-a" și "a"
ROMAN_CORE = r'(?=[MDCLXVI]+(?:-lea|-a|lea|a|\b))M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})'

# REGULA 1: Pentru secole (ex: Secolul XX, clasa a X-a va fi prinsă de regula 2)
SECOL_ROMAN_REGEX = re.compile(
    rf'\b(secol\w*(?:\s+(?:al|a))?)\s+({ROMAN_CORE})(?:(-lea|-a|lea|a))?\b',
    re.IGNORECASE
)

# REGULA 2: Pentru ordinale romane generale, atât masculin "al" cât și feminin "a" (ex: Carol al II-lea, clasa a X-a)
ORDINAL_ROMAN_REGEX = re.compile(
    rf'\b(al|a)\s+({ROMAN_CORE})(?:(-lea|-a|lea|a))?\b',
    re.IGNORECASE
)

ROMANIAN_WORDS = {"vii", "mii", "mi", "vi", "ci", "di", "li", "c", "d", "m", "l", "x"}
ACRONYMS = {"cd", "cv", "mc", "md", "dc"}


def roman_to_int(s):
    roman_dict = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = s.upper()
    total, prev = 0, 0
    for char in reversed(s):
        curr = roman_dict.get(char, 0)
        if curr < prev:
            total -= curr
        else:
            total += curr
        prev = curr
    return total


def convert_numbers_in_text(text):
    def replace_roman(match):
        prefix = match.group(1) 
        word = match.group(2)   

        suffix = match.group(3) if match.lastindex and match.lastindex >= 3 and match.group(3) else ""
        

        if not word.isupper():
            return match.group(0)
            
        word_lower = word.lower()
        if word_lower in ACRONYMS:
            return match.group(0)
                
        try:
            converted_number = num2words(roman_to_int(word), lang='ro').lower()
            
            clean_suffix = suffix.replace("-", "")
            return f"{prefix} {converted_number}{clean_suffix}"
        except Exception:
            return match.group(0)


    text = SECOL_ROMAN_REGEX.sub(replace_roman, text)

    text = ORDINAL_ROMAN_REGEX.sub(replace_roman, text)

    def replace_digit(match):
        return num2words(int(match.group(0)), lang='ro').lower()


    text = re.sub(r'\d+', replace_digit, text)
    

    text = re.sub(r'(\b\w+)-lea\b', r'\1lea', text, flags=re.IGNORECASE)
    
    # Pentru "-a" folosim FILTRUL DE SIGURANȚĂ: ștergem cratima DOAR dacă cuvântul din stânga este un număr
    safe_number_endings = r'(unu|doi|trei|patru|cinci|șase|șapte|opt|nouă|zece|sprezece|zeci|sută|sute|mie|mii|milion|milioane)'
    text = re.sub(rf'(\b\w*{safe_number_endings})-a\b', r'\1a', text, flags=re.IGNORECASE)
    
    return text


def process_line(line):
    try:
        obj = json.loads(line)
        if "text" in obj:
            obj["text"] = convert_numbers_in_text(obj["text"])
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return line.strip()


def process_chunk(chunk_lines):
    return [process_line(line) for line in chunk_lines]


def chunk_generator(filepath, chunk_size):
    with open(filepath, 'r', encoding='utf-8') as f:
        chunk = []
        for line in f:
            chunk.append(line)
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk


def count_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)


def main():
    parser = argparse.ArgumentParser(
        description="Normalizează numerele dintr-un manifest JSONL: "
                    "cifrele (123 → 'o sută douăzeci...'), "
                    "secolele romane (Secolul XX → 'Secolul douăzeci'), "
                    "ordinale romane masculin și feminin (al II-lea → 'al doilea', a X-a → 'a zecea'). "
                    "Fișierul original va fi suprascris (in-place) în siguranță."
    )
    parser.add_argument("input_manifest", help="Fișier manifest JSONL (va fi suprascris)")
    parser.add_argument("chunk_size", type=int, nargs="?", default=50000,
                        help="Linii per chunk multiprocessing (default: 50000)")
    parser.add_argument("num_workers", type=int, nargs="?", default=None,
                        help="Număr de procese worker (default: cpu_count()-1)")
    args = parser.parse_args()

    import multiprocessing
    num_workers = args.num_workers or max(1, multiprocessing.cpu_count() - 1)

    input_path = os.path.abspath(args.input_manifest)
    total = count_lines(input_path)
    print(f"Total linii: {total} | Workers: {num_workers} | Chunk size: {args.chunk_size}")

    pool = ProcessPoolExecutor(max_workers=num_workers)

    dir_name = os.path.dirname(input_path)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fout:
            with tqdm(total=total, desc="Normalizare", unit="linii") as pbar:
                for processed_chunk in pool.map(process_chunk, chunk_generator(input_path, args.chunk_size)):
                    for processed_line in processed_chunk:
                        fout.write(processed_line + '\n')
                    pbar.update(len(processed_chunk))
        
        pool.shutdown()
        os.replace(temp_path, input_path)
        print(f"Gata! Fișierul a fost suprascris cu succes: {args.input_manifest}")

    except Exception as e:
        pool.shutdown()
        os.remove(temp_path)
        print(f"Eroare în timpul procesării. Fișierul original a rămas intact. Eroare: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()