import json
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Filtrează un manifest JSONL, eliminând înregistrările cu o rată "
                    "de vorbire anormală (ex: < 0.1 sau > 5 cuvinte/secundă). "
                    "Rezultatul va fi salvat într-un fișier nou."
    )
    parser.add_argument("input_manifest", help="Fișier manifest JSONL de intrare")
    parser.add_argument("output_manifest", help="Fișier manifest JSONL de ieșire")
    parser.add_argument("--min-wps", type=float, default=0.1,
                        help="Numărul minim de cuvinte pe secundă pentru a păstra linia (default: 0.1)")
    parser.add_argument("--max-wps", type=float, default=5.0,
                        help="Numărul maxim de cuvinte pe secundă pentru a păstra linia (default: 5.0)")
    
    args = parser.parse_args()

    total_linii = 0
    linii_pastrate = 0
    linii_eliminate = 0

    print(f"Rată acceptată: {args.min_wps} - {args.max_wps} cuvinte/secundă")
    print(f"Intrare: {args.input_manifest}")
    print(f"Ieșire:  {args.output_manifest}\n")

    try:
        with open(args.input_manifest, 'r', encoding='utf-8') as f_in, \
             open(args.output_manifest, 'w', encoding='utf-8') as f_out:

            for line in f_in:
                total_linii += 1
                try:
                    data = json.loads(line)
                    
                    # Extragem textul și durata
                    text = data.get("text", "").strip()
                    duration = data.get("duration", 0.0)

                    # Evităm împărțirea la zero și excludem fișierele fără durată validă
                    if duration > 0:
                        numar_cuvinte = len(text.split())
                        cuvinte_pe_secunda = numar_cuvinte / duration

                        if args.min_wps <= cuvinte_pe_secunda <= args.max_wps:
                            f_out.write(line)
                            linii_pastrate += 1
                        else:
                            linii_eliminate += 1
                    else:
                        # Dacă durata este 0 sau lipsește, eliminăm linia
                        linii_eliminate += 1

                except json.JSONDecodeError:
                    continue

                if total_linii % 100000 == 0:
                    print(f"Procesate: {total_linii} | Păstrate: {linii_pastrate} | Eliminate: {linii_eliminate}")

        print(f"\nRAPORT: {total_linii} inițial → {linii_pastrate} păstrate | {linii_eliminate} eliminate")
        print("Filtrarea s-a încheiat cu succes.")

    except Exception as e:
        print(f"\nA apărut o eroare în timpul procesării: {e}")


if __name__ == "__main__":
    main()