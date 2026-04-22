# Doxygen API Docs Generation

This folder contains the Doxygen configuration used to turn API markdown docs into a browsable HTML site.

## Prerequisites

- Install [Doxygen](https://www.doxygen.nl/download.html).

Windows examples:

```powershell
winget install --id DimitriVanHeesch.Doxygen -e
```

or:

```powershell
choco install doxygen.install -y
```

## Generate docs

From repository root:

```powershell
doxygen docs/doxygen/Doxyfile
```

Generated output:

- `docs/generated/html/index.html`

## Notes

- Source markdown pages are under `docs/api-pre-security`.
- `mainpage.md` is used as the landing page for the generated docs site.
