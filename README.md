# Asymptote Dataset Annotation and Export Pipeline

This repository provides a workflow for cleaning and annotating math-to-diagram training data using [Label Studio](https://labelstud.io/), and exporting the results back into a fine-tuning–ready format.

## Repository Structure

```
.
├── label_studio.py           # Script to create a Label Studio project and import tasks
├── label_studio_export.py    # Script to export annotations and inject edits into JSONL
├── data/                     # Raw/flat-turn conversation JSON files
│   └── turns_train.json
│   └── turns_val.json
├── data_finetune/            # Fine-tuning format (JSONL) files
│   └── train_sk_01.jsonl
│   └── val_sk_01.jsonl
│   └── train_sk_02.jsonl     # Created after running the export script
│   └── val_sk_02.jsonl       # Created after running the export script
```

- **data/**: Contains flattened conversation data (`flat_turn` JSON), with each math problem–response pair represented as structured turns.  
- **data_finetune/**: Contains fine-tuning JSONL files in OpenAI-compatible format, one message-pair per line.  
- **label_studio.py**: Automates project creation in Label Studio and imports the dataset for annotation.  
- **label_studio_export.py**: Downloads completed annotations, merges them into the original dataset, and outputs corrected fine-tuning files.  

## Workflow

### 1. Create and Configure a Project
Run `label_studio.py` to:
- Connect to your Label Studio instance (update `LABEL_STUDIO_URL` and `API_KEY` first).  
- Create a new project with a custom labeling interface designed for math problems and Asymptote code.  
- Import `data/turns_train.json` as the initial dataset.  
- Update the project configuration to display math questions, generated code, and preview fields for editing.  

### 2. Annotate Data in Label Studio
Use Label Studio’s web interface to:
- Edit user questions or assistant code directly in the provided text areas.  
- Compare the generated Asymptote code against rendered diagrams.  
- Save corrections for each conversation turn.  

### 3. Export and Merge Annotations
Run `label_studio_export.py` to:
- Pull project annotations from Label Studio (either direct export or via an export job).  
- Merge edited fields back into the flattened dataset (`turns_train.json`).  
- Inject the edits into the original fine-tuning JSONL file, producing a corrected copy in `data_finetune/`.  

Example:
```bash
python label_studio_export.py
```

This will create a corrected JSONL file (e.g., `val_sk_02.jsonl`) that preserves original fields and updates edited turns.

## Key Functions

- **generate_label_config** (`label_studio.py`): Builds the custom XML/HTML interface for Label Studio tasks.  
- **parse_label_studio_edits** (`label_studio_export.py`): Parses annotation exports into a usable dictionary keyed by turn ID.  
- **inject_edits_into_jsonl** (`label_studio_export.py`): Applies edits back into the fine-tuning dataset, ensuring format consistency.  

## Next Steps / Improvements
- Integrate compiled Asymptote image previews directly into the annotation UI for faster quality control.  
- Add logging (via `logging` module) instead of print statements for better reproducibility.  
- Streamline annotation export into batch jobs for large datasets.  
