# Design: language-aware-image-descriptions

## High-Level Architecture and Data Flow

1. **Current flow (relevant segment)**
   - `handler.py` runs marker conversion, optional OCR correction (`process_file`), then optional image description (`describe_images`), and finally inserts wrappers via `insert_image_descriptions_to_text_file(...)`.
   - Language for image descriptions and wrappers is currently implicit and defaults to English.

2. **Proposed flow**
   - After successful text post-processing for each output file, infer a **single per-file target language** from the output text.
   - Resolve localized wrapper strings (section heading, begin marker, end marker) for that language.
   - Pass target language to `vllm_worker.describe_images(...)`.
   - Compose model prompts with explicit language directive so the LLM outputs descriptions in the resolved language.
   - Insert descriptions using localized wrappers.

3. **Data path (per file)**
   - `processed_file_path` text -> `infer_output_language(...)` in `handler.py`
   - resolved language -> `vllm_worker.describe_images(..., target_language=...)`
   - resolved language -> `insert_image_descriptions_to_text_file(..., localization=...)`
   - localized wrappers + generated text -> updated markdown/txt output

## Planned File-Level Changes

1. **`handler.py`**
   - Add helper(s) for language inference and normalization:
     - `infer_output_language(text: str) -> str` — uses `langdetect` with seeded determinism (seed=0). Operates on a text sample (first ~2000 characters) for performance on large documents.
     - Helper for mapping language codes to human-readable names (for prompt use).
   - Add localized-wrapper resolver:
     - e.g., `resolve_image_description_labels(language: str, app_config: GlobalConfig) -> dict[str, str]`
     - Contains a built-in localization map for initial language set (see Supported Languages below).
     - Falls back to English labels when a detected language has no localization entry.
   - Extend `insert_image_descriptions_to_text_file` signature with optional label-override parameters (e.g., `heading_override`, `end_override`, `section_heading_override`) that default to `app_config` values. This is required because `GlobalConfig` wrapper fields are `frozen=True` and cannot be mutated at runtime.
   - In the post-processing loop, infer language once per file and pass to both image description generation and insertion.
   - Add logging for the selected language and fallback path.

2. **`vllm_worker.py`**
   - Extend image-description API signatures with optional language argument:
     - `describe_images(..., target_language: Optional[str] = None)`
     - `_describe_images_async(..., target_language: Optional[str] = None)`
     - `_describe_single_image_async(..., target_language: Optional[str] = None)`
   - Add a prompt-composition helper to merge:
     - system prompt template (default or custom),
     - explicit language instruction appended as the **final sentence** of the system prompt (e.g., `"Respond in {language}."`).
     - Composition rule: the language directive is always appended last, whether the system prompt is the default or a custom `prompt_template`. This ensures the language instruction is not overridden by earlier prompt text.
     - The `user_instruction` string remains in English (models reliably follow English instructions even when outputting in other languages).
   - Ensure token budget calculations account for added language instruction text.

3. **`settings.py` (optional/minimal extension)**
   - Keep existing global English defaults as fallback.
   - Option A (minimal-code): implement localization map in `handler.py`.
   - Option B (configurable): add optional environment-configurable localized labels map.
   - Preferred for initial implementation: **Option A**, because localization is per-file and dynamic, while `GlobalConfig` fields are frozen at startup and env-configured. A runtime-configurable map would require a different config mechanism that is out of scope for the initial implementation.

4. **`test/`**
   - Add/update tests for:
     - per-file language inference/fallback,
     - language propagation to worker calls,
     - prompt includes explicit language instruction,
     - localized wrapper insertion in both inline and fallback-append paths.

## API / Schema / Dependency Impact

1. **Public behavior impact**
   - No breaking change required: new language parameters are optional.
   - Existing callers of `VllmWorker.describe_images(...)` remain valid.

2. **Configuration impact**
   - No mandatory new job-input fields.
   - Fallback language remains English if language inference cannot resolve confidently.

3. **Dependency impact**
   - Add `langdetect` to `requirements.txt` (lightweight, pure-Python, well-maintained).
   - Seed `DetectorFactory.seed = 0` at module level in `handler.py` for deterministic results (NFR-1).

## Supported Languages (Initial Set)

The localization map covers common European book-scan languages. If a detected language is not in this map, English labels are used as fallback.

| Code | Language   | Section Heading Example             | Begin Marker Example                    | End Marker Example                    |
|------|------------|--------------------------------------|-----------------------------------------|---------------------------------------|
| en   | English    | ## Extracted Image Descriptions      | **[BEGIN IMAGE DESCRIPTION]**           | **[END IMAGE DESCRIPTION]**           |
| de   | German     | ## Extrahierte Bildbeschreibungen    | **[BEGINN BILDBESCHREIBUNG]**           | **[ENDE BILDBESCHREIBUNG]**           |
| fr   | French     | ## Descriptions d'images extraites   | **[DÉBUT DESCRIPTION IMAGE]**           | **[FIN DESCRIPTION IMAGE]**           |
| es   | Spanish    | ## Descripciones de imágenes         | **[INICIO DESCRIPCIÓN DE IMAGEN]**      | **[FIN DESCRIPCIÓN DE IMAGEN]**       |
| it   | Italian    | ## Descrizioni delle immagini        | **[INIZIO DESCRIZIONE IMMAGINE]**       | **[FINE DESCRIZIONE IMMAGINE]**       |
| pt   | Portuguese | ## Descrições de imagens extraídas   | **[INÍCIO DESCRIÇÃO DA IMAGEM]**        | **[FIM DESCRIÇÃO DA IMAGEM]**         |
| nl   | Dutch      | ## Geëxtraheerde afbeeldingsbeschrijvingen | **[BEGIN AFBEELDINGBESCHRIJVING]** | **[EINDE AFBEELDINGBESCHRIJVING]**    |
| pl   | Polish     | ## Opisy wyodrębnionych obrazów      | **[POCZĄTEK OPISU OBRAZU]**             | **[KONIEC OPISU OBRAZU]**             |
| cs   | Czech      | ## Popisy extrahovaných obrázků      | **[ZAČÁTEK POPISU OBRÁZKU]**            | **[KONEC POPISU OBRÁZKU]**            |
| ru   | Russian    | ## Описания извлечённых изображений  | **[НАЧАЛО ОПИСАНИЯ ИЗОБРАЖЕНИЯ]**       | **[КОНЕЦ ОПИСАНИЯ ИЗОБРАЖЕНИЯ]**      |

## Compatibility and Rollout Notes

1. Keep the localization scope focused on image-description wrappers and prompts only.
2. Preserve existing behavior for non-text outputs and files with no extracted images.
3. Prefer deterministic inference/fallback over probabilistic non-deterministic selection.
4. `langdetect.DetectorFactory.seed` must be set to `0` at module initialization for deterministic behavior.
5. `infer_output_language` operates on a sample (first ~2000 characters) for performance on large documents.
