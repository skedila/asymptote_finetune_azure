from label_studio_sdk import LabelStudio
import requests, json, re
from typing import Dict, List, Any

# Helper Functions

def normalize_for_markdown(s: str, fence: bool = False, lang_hint: str = "asymptote") -> str:
    """
    Normalize double-escaped content into display-ready text for markdown renderers.
    - Turns '\\n'->'\n', '\\t'->'\t', '\\"'->'"'
    - Optionally wraps in triple backticks for consistent code rendering.
    """
    if not isinstance(s, str):
        return s

    s = s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')

    if fence:
        stripped = s.strip()
        if not (stripped.startswith("```") and stripped.endswith("```")):
            s = f"```{lang_hint}\n{s}\n```"
    return s


def parse_label_studio_edits(export_data: List[Dict[str, Any]]) -> Dict[int, Dict[str, str]]:
    """
    Extract edited text values from Label Studio export into:
      { turn_id: { 'user': '...', 'chat_text': '...', 'reasoning': '...', 'tool_name': '...', ... } }

    We look at 'result[].from_name' patterns like:
      assistant_{tid}, assistant_reasoning_{tid}, user_{tid}, tool_name_{tid}, tool_{tid}, assistant_tool_{tid}
    and map them to output fields via 'from_name_map'.
    """
    from_name_map = {
        'assistant_reasoning': 'reasoning',
        'assistant_tool': 'assistant_tool',
        'assistant': 'chat_text',
        'tool_name': 'tool_name',
        'tool': 'tool',
        'user': 'user',
    }

    edits_by_turn: Dict[int, Dict[str, str]] = {}

    for item in export_data or []:
        for ann in item.get('annotations', []):
            for res in ann.get('result', []):
                fn = res.get('from_name')
                texts = res.get('value', {}).get('text', [])
                if not fn or not texts:
                    continue
                # Identify the prefix (field group) and the turn id suffix
                for prefix, field in from_name_map.items():
                    if fn.startswith(prefix + '_'):
                        m = re.search(rf'{prefix}_(\d+)$', fn)
                        if not m:
                            # Sometimes from_name could carry extra postfix; loosen the regex if needed:
                            m = re.search(rf'{prefix}_(\d+)', fn)
                        if not m:
                            continue
                        tid = int(m.group(1))
                        edits_by_turn.setdefault(tid, {})[field] = texts[0]
                        break

    return edits_by_turn


def label_studio_to_flat_convo(flat_turns: List[Dict[str, Any]], export_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge edited text from Label Studio export into flat conversation turns.

    Returns a new list with edits applied
    """
    for idx, turn in enumerate(flat_turns):
        turn['turn_id'] = idx

    edits_by_turn = parse_label_studio_edits(export_data)

    # Merge edits
    merged = []
    for turn in flat_turns:
        tid = turn['turn_id']
        base = {'turn_id': tid, 'conversation_id': turn.get('conversation_id')}
        for field in ['user', 'image_url', 'tool_id', 'tool_name', 'assistant_tool', 'tool', 'chat_text', 'reasoning']:
            if tid in edits_by_turn and field in edits_by_turn[tid]:
                base[field] = edits_by_turn[tid][field]
            else:
                base[field] = turn.get(field, '')
        merged.append(base)
    return merged


# Create a cope of the original finetune JSONL and inject LS edits
def inject_edits_into_jsonl(
    orig_jsonl_path: str,
    output_jsonl_path: str,
    flat_turns: List[Dict[str, Any]],
    export_data: List[Dict[str, Any]],
    normalize_for_markdown: bool = True,
    fence_code: bool = False,
    lang_hint: str = "asymptote"
) -> None:
    """
    Read the original finetune jsonl and inject Label Studio edits back into each line, writing a corrected copy.
    Non-edited fields are left untouched.
    """
    # Build turn_id order from flat_turns (line index -> turn_id)
    if not flat_turns:
        raise ValueError("flat_turns is empty; cannot align LS edits to original JSONL.")

    # If any turn lacks turn_id, populate sequentially
    for i, t in enumerate(flat_turns):
        t['turn_id'] = i

    order_turn_ids = [t['turn_id'] for t in flat_turns]

    # Parse edits keyed by turn_id
    edits_by_turn = parse_label_studio_edits(export_data)

    updated_count = 0
    total_lines = 0

    with open(orig_jsonl_path, "r", encoding="utf-8") as fin, \
         open(output_jsonl_path, "w", encoding="utf-8") as fout:

        for idx, line in enumerate(fin):
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Preserve malformed lines as-is 
                fout.write(line + "\n")
                continue

            msgs = obj.get("messages", [])
            # Guard: if this line doesn't look like the finetune format, then copy through
            if not isinstance(msgs, list) or not msgs:
                fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
                continue

            # Map: this line's turn_id
            try:
                tid = order_turn_ids[idx]
            except IndexError:
                # If there are more lines than flat_turns, then copy through
                fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
                continue

            edits = edits_by_turn.get(tid, {})

            # Extract pointers to user/assistant messages
            user_msg = next((m for m in msgs if m.get("role") == "user"), None)
            asst_msg = next((m for m in msgs if m.get("role") == "assistant"), None)

            # Apply user edit
            if "user" in edits and user_msg is not None:
                new_user = edits["user"]
                if normalize_for_markdown:
                    new_user = normalize_for_markdown(new_user, fence=False)
                user_msg["content"] = new_user
                updated_count += 1

            # Apply assistant edit (chat_text)
            if "chat_text" in edits and asst_msg is not None:
                new_code = edits["chat_text"]
                if normalize_for_markdown:
                    new_code = normalize_for_markdown(new_code, fence=fence_code, lang_hint=lang_hint)

                asst_msg["content"] = new_code
                updated_count += 1

            # Preserve everything else
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"Injected edits into {updated_count} fields across {total_lines} lines -> {output_jsonl_path}")


def export_from_label_studio(base_url, api_key, project_id):
    headers = {
        'Authorization': f'Token {api_key}',
        'Content-Type': 'application/json'
    }

    # Method 1: direct export
    export_url = f'{base_url}/api/projects/{project_id}/export'
    response = requests.get(export_url, headers=headers, params={'exportType': 'JSON'})
    if response.status_code == 200:
        return response.json()

    # Method 2: if Method 1 fails, create export job then download
    create_export_url = f'{base_url}/api/projects/{project_id}/exports'
    export_payload = {"export_type": "JSON"}
    create_response = requests.post(create_export_url, headers=headers, json=export_payload)

    if create_response.status_code in [200, 201]:
        export_id = create_response.json().get('id')
        download_url = f'{base_url}/api/projects/{project_id}/exports/{export_id}/download'
        download_response = requests.get(download_url, headers=headers)
        if download_response.status_code == 200:
            return download_response.json()

    return None


base_url = "https://label-studio-814801174874.us-central1.run.app"
api_key = "<LEGACY_TOKEN>"
project_id = 0 # CHANGE ID

# Files
orig_jsonl_path = "data_finetune/val_sk_01.jsonl"  # original finetuning JSONL (one turn per line)
corrected_jsonl_path = "data_finetune/val_sk_02.jsonl" # output copy with edits injected
export_path = "data/ls_export.json" # store raw LS export
flat_path = "data/turns_train.json" # flat tursn file
orig_path = orig_jsonl_path
out_path = corrected_jsonl_path

# Step 1: Pull LS export
ls = LabelStudio(base_url=base_url, api_key=api_key)
_ = ls.projects.get(id=project_id)
export_data = export_from_label_studio(base_url, api_key, project_id)

# Save raw export (optional)
with open(export_path, "w", encoding="utf-8") as f:
    json.dump(export_data, f, indent=2)

# Step 2: Load flat turns
with open(flat_path, "r", encoding="utf-8") as f:
    flat_data = json.load(f)

flat_turns = flat_data.get("turns", [])
if not flat_turns:
    raise RuntimeError("Flat turns file missing or empty.")

# Step 3.1:
merged_turns = label_studio_to_flat_convo(flat_turns, export_data)

# Step 3.2 Inject edits back into original finetune JSONL (corrected copy):
inject_edits_into_jsonl(
    orig_jsonl_path=orig_jsonl_path,
    output_jsonl_path=corrected_jsonl_path,
    flat_turns=flat_turns,
    export_data=export_data,
    normalize_for_markdown=True, # fixes \\n, \\"
    fence_code=False, # set True to wrap assistant code in ```asymptote ... ```
    lang_hint="asymptote"
)

print("Label Studio Annotations successfully exported!")
