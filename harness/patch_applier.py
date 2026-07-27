import re
import os

def apply_patch(original_content: str, patch_text: str) -> str:
    """
    Applies a patch containing one or more SEARCH/REPLACE blocks.
    
    Format:
    <<<<<<< SEARCH
    old code
    =======
    new code
    >>>>>>> REPLACE
    """
    pattern = re.compile(
        r'<<<<<<< SEARCH\n(.*?)\n?=======\n(.*?)\n?>>>>>>> REPLACE',
        re.DOTALL
    )
    
    matches = pattern.finditer(patch_text)
    patched_content = original_content
    match_found = False
    
    for match in matches:
        match_found = True
        search_block = match.group(1)
        replace_block = match.group(2)
        
        if search_block not in patched_content:
            raise ValueError(f"Search block not found in original content:\n{search_block}")
            
        # Replace only the first occurrence
        patched_content = patched_content.replace(search_block, replace_block, 1)
        
    if not match_found:
        raise ValueError("No valid SEARCH/REPLACE blocks found in patch text.")
        
    return patched_content

def apply_patch_to_file(file_path: str, patch_text: str):
    """Reads file, applies patch, and writes back the modified content."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    new_content = apply_patch(content, patch_text)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
