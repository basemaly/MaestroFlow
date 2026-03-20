import subprocess
import json
import sys

LIBRARY_PATH = "/Volumes/BA/MEDIA/Calibre-Clean/ALL-Clean"
CALIBREDB_CMD = "/Applications/calibre.app/Contents/MacOS/calibredb"

def main():
    print("Fetching books from library...")
    # Get all books with their languages
    result = subprocess.run(
        [CALIBREDB_CMD, "list", "--library-path", LIBRARY_PATH, "-f", "languages", "--for-machine"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error fetching books: {result.stderr}")
        sys.exit(1)
        
    books = json.loads(result.stdout)
    to_update = []
    
    for book in books:
        langs = book.get("languages")
        
        needs_update = False
        if not langs:
            needs_update = True
        elif not isinstance(langs, list):
            needs_update = True
        elif len(langs) != 1 or langs[0] != "eng":
            needs_update = True
            
        if needs_update:
            to_update.append(book["id"])
            
    print(f"Found {len(to_update)} books requiring language normalization to 'eng'.")
    
    # Process batch
    for i, book_id in enumerate(to_update):
        print(f"[{i+1}/{len(to_update)}] Updating book ID {book_id} to 'eng'...")
        update_result = subprocess.run(
            [CALIBREDB_CMD, "set_metadata", "--library-path", LIBRARY_PATH, "-f", "languages:eng", str(book_id)],
            capture_output=True,
            text=True
        )
        if update_result.returncode != 0:
            print(f"  Error updating book {book_id}: {update_result.stderr}")

    print("Language normalization complete.")

if __name__ == "__main__":
    main()
