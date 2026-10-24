## What changed

<!-- Describe the user-visible behavior and the smallest useful scope. -->

## Why

<!-- Link an issue or explain the learning/maintenance outcome. -->

## Validation

- [ ] `python -m compileall -q app tests scripts` (if backend changed)
- [ ] `python -m unittest discover -s tests -v` (if backend behavior changed)
- [ ] `npm run build` (if frontend changed)
- [ ] `npm test` (if frontend behavior changed)
- [ ] Documentation and capability boundaries updated

## Risk and rollout

<!-- Mention migrations, feature flags, external credentials, or rollback steps. -->

## Checklist

- [ ] No secrets, generated databases, logs, cookies or private data included
- [ ] Public-source and authorization rules are preserved
- [ ] New external dependencies are documented
- [ ] Screenshots or a reproducible command are included for UI changes
