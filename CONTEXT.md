# procure-ai

A claim-assessment system: users upload contractor Payment Claim PDFs into a Project; a
phase-based Harness pipeline parses each PDF into a structured Claim and Assessment.

## Language

**Document**:
The durable, persisted source PDF a user uploads into a Project for processing.
Stored once with its raw bytes; referenced by every Harness Session that processes it.
_Avoid_: file, upload, attachment, input_file

**Harness Session**:
A single execution of the parsing pipeline over one Document, walking a fixed sequence
of Phases and producing Workspace Files.
_Avoid_: run, job, task

**Phase**:
One step in a Harness Session (programmatic or LLM), consuming and producing Workspace Files.

**Workspace File**:
A derived artifact produced by a Phase (e.g. `raw_extraction.json`), scoped to one
Harness Session. Not the source PDF.
_Avoid_: document, output file

**Claim**:
The structured record produced at the end of a successful Harness Session from a Document.

**Re-run**:
Recovery action when a Harness Session fails: re-trigger the pipeline over the same
Document. Because a Claim is only written at the end, a failed Session has produced no
Claim, so a Re-run deletes nothing.
_Avoid_: retry, reprocess

## Relationships

- A **Project** contains many **Documents** and many **Claims**
- A **Document** is processed by one or more **Harness Sessions** (failed attempts + at most one success)
- A **Harness Session** references exactly one **Document** and produces at most one **Claim** (only on success)
- Deleting a **Harness Session** never deletes its **Document** (FK points Session → Document)
- Deleting a **Claim** deletes its **Document**, which cascades away every **Harness Session** on it
- A **Document** is otherwise durable for the life of the **Project**

## Flagged ambiguities

- "document table" was used to mean a new table holding the uploaded PDF — resolved: the
  source PDF is a **Document**; the existing `harness_workspace_files` holds **Workspace
  Files** (derived artifacts), a distinct concept.
- "loaded into memory, not persisted" — resolved: the PDF was written to ephemeral temp
  disk, not memory. The defect is ephemeral storage, not in-memory-only.
