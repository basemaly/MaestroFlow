import subprocess
import json
import os
import sys

LIBRARY_PATH = "/Volumes/BA/MEDIA/Calibre-Clean/ALL-Clean"
CALIBREDB_CMD = "/Applications/calibre.app/Contents/MacOS/calibredb"
FETCH_CMD = "/Applications/calibre.app/Contents/MacOS/fetch-ebook-metadata"

def get_cover_size(cover_path):
    if not cover_path or not os.path.exists(cover_path):
        return 0
    return os.path.getsize(cover_path)

def main():
    print("Fetching books for cover analysis...")
    result = subprocess.run(
        [CALIBREDB_CMD, "list", "--library-path", LIBRARY_PATH, "-f", "title,authors,identifiers,cover", "--for-machine"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error fetching books: {result.stderr}")
        sys.exit(1)
        
    books = json.loads(result.stdout)
    to_update = []
    
    # Identify books with no cover or low-res cover (< 50KB)
    for book in books:
        cover_path = book.get("cover")
        size = get_cover_size(cover_path)
        
        # 50KB = 50 * 1024 = 51200 bytes
        if size < 51200:
            to_update.append(book)
            
        if len(to_update) >= 50:
            break
            
    print(f"Found {len(to_update)} books needing new covers. Processing batch...")
    
    for i, book in enumerate(to_update):
        book_id = book["id"]
        title = book.get("title", "")
        authors = book.get("authors", "")
        # calibredb list returns author or authors (string or list depending on version)
        if isinstance(authors, list):
            authors_str = " & ".join(authors)
        else:
            authors_str = authors
            
        identifiers = book.get("identifiers", {})
        isbn = identifiers.get("isbn", "") if isinstance(identifiers, dict) else ""
        
        print(f"[{i+1}/{len(to_update)}] Fetching cover for '{title}' (ID {book_id})...")
        
        temp_cover = f"temp_cover_{book_id}.jpg"
        
        # Build command
        cmd = [FETCH_CMD]
        if title:
            cmd.extend(["-t", title])
        if authors_str:
            cmd.extend(["-a", authors_str])
        if isbn:
            cmd.extend(["-i", isbn])
            
        cmd.extend(["-c", temp_cover])
        
        fetch_result = subprocess.run(cmd, capture_output=True, text=True)
        
        if os.path.exists(temp_cover):
            print(f"  Successfully downloaded cover. Applying to book {book_id}...")
            # Apply to Calibre DB
            update_result = subprocess.run(
                [CALIBREDB_CMD, "set_metadata", "--library-path", LIBRARY_PATH, "-f", f"cover:{temp_cover}", str(book_id)],
                capture_output=True,
                text=True
            )
            if update_result.returncode != 0:
                print(f"  Error setting cover: {update_result.stderr}")
            else:
                print(f"  Cover applied.")
                
            os.remove(temp_cover)
        else:
            print(f"  Failed to find a new cover online. (Return code: {fetch_result.returncode})")

    print("Cover quality sweep complete.")

if __name__ == "__main__":
    main()
