"""The kaizen hook entries as a home's ``.pre-commit-config.yaml`` holds them, written out by hand
so the tests check the synced doc and ``home init`` against a literal."""

HOOK_ENTRIES = """\
  - repo: local
    hooks:
      - id: kaizen-leak-check
        name: kaizen leak check
        entry: kaizen hook leak-check
        language: system
        pass_filenames: false
      - id: kaizen-no-commit-to-branch
        name: kaizen no commit to branch
        entry: kaizen hook no-commit-to-branch
        language: system
        pass_filenames: false
        always_run: true
      - id: kaizen-prose-marks
        name: kaizen prose marks
        entry: kaizen hook prose-marks
        language: system
      - id: kaizen-section-banners
        name: kaizen section banners
        entry: kaizen hook section-banners
        language: system
      - id: kaizen-work-tracking
        name: kaizen work-tracking references
        entry: kaizen hook work-tracking
        language: system
"""
