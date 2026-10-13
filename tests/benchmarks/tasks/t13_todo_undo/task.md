The folder is a small to-do list program (`models.py`, `store.py`, `cli.py` and `test_store.py` in one folder). Add **undo and redo** to it. Read the existing code first and keep its style; every existing test must keep passing.

**Store (`store.py`)**
- Every successful `add`, `complete` and `remove` is one undoable step. Calls that fail (empty title, unknown id) are not steps. `complete` on a task that is already done changes nothing and is not a step.
- `undo() -> bool` reverts the most recent step that has not been undone and returns `True`; with nothing to undo it returns `False` and changes nothing (no exception). `redo() -> bool` re-applies the most recently undone step the same way.
- Undo restores the exact previous state, including the id counter: after undoing an `add`, the next `add` gets the same id again. Redo restores the state after the step.
- Any new step (`add`, `complete`, `remove`) clears the redo history.
- At most 20 steps are kept; when a 21st step is made the oldest is forgotten (you cannot undo past it).
- History is saved in the same JSON file under the key `"history"` as `{"undo": [...], "redo": [...]}`, so a new `TaskStore(path)` on the same file can still undo and redo. The existing keys `"next_id"` and `"tasks"` and their format must not change, and a file written by the old version (no `"history"` key) must load with empty history. An in-memory store (no path) has history too.

**CLI (`cli.py`)**
- New commands `undo` and `redo`. They print `Undone.` / `Redone.` on success, or `Nothing to undo.` / `Nothing to redo.` when there is nothing, and exit with 0 either way.
- `main(argv, store_path)` and the other commands behave as before.

Write tests for the new behaviour too (add them to `test_store.py` or a new test file). Use only the standard library.
