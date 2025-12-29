# RCT Finder

A production-quality Python tool to find randomized controlled trials (RCTs) published in the last N days across major medical journals worldwide.

## Features

- **Multi-source search**: PubMed, Semantic Scholar, Europe PMC, Crossref, OpenAlex
- **Optional enterprise sources**: Scopus, Web of Science, Dimensions (with API keys)
- **Smart RCT detection**: Uses publication type filters when available, text-based detection as fallback
- **Cross-source deduplication**: DOI → PMID/PMCID → fuzzy title+author+year matching
- **Topic classification**: Cardiology, Gastroenterology, Other/Unclear (rules-based)
- **Rich output**: Formatted Excel + mirrored CSV with full provenance tracking

## Installation

```bash
# Navigate to the package directory
cd rct_finder

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Basic usage - find RCTs from the last 30 days
python -m rct_finder --days 30 --output results.xlsx

# With API keys for better rate limits
python -m rct_finder --days 30 \
    --ncbi-api-key YOUR_NCBI_KEY \
    --semantic-scholar-api-key YOUR_S2_KEY \
    --output results.xlsx

# Limited search for testing
python -m rct_finder --days 7 --max-records-per-source 10 --output test_results.xlsx
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days`, `-d` | 30 | Number of days to look back |
| `--output`, `-o` | rct_results.xlsx | Output Excel file path |
| `--max-records-per-source` | unlimited | Limit records per source |
| `--include-preprints` | false | Include preprints |
| `--query`, `-q` | none | Additional search terms |
| `--sources` | all | Specific sources to query |
| `--verbose`, `-v` | false | Verbose logging |

### API Keys

| Option | Environment Variable | Description |
|--------|---------------------|-------------|
| `--ncbi-api-key` | `NCBI_API_KEY` | PubMed rate limit: 10 req/sec (vs 3) |
| `--semantic-scholar-api-key` | `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar |
| `--scopus-api-key` | `SCOPUS_API_KEY` | Scopus (Elsevier) |
| `--wos-api-key` | `WOS_API_KEY` | Web of Science |
| `--dimensions-api-key` | `DIMENSIONS_API_KEY` | Dimensions |

## Output Columns

| Column | Description |
|--------|-------------|
| `source_primary` | First source that found this record |
| `sources_found_in` | All sources that found this record |
| `pmid`, `pmcid`, `doi`, `s2PaperId`, `openalex_id` | Source-specific identifiers |
| `title`, `authors`, `journal`, `issn` | Core metadata |
| `publication_date`, `publication_year` | Publication timing |
| `abstract`, `mesh_terms`, `keywords`, `fields_of_study` | Content metadata |
| `rct_flag`, `rct_detection_method` | RCT detection results |
| `topic`, `classification_reason` | Topic classification |
| `data_quality_notes` | Any data quality issues |

## Architecture

```
rct_finder/
├── connectors/          # Data source connectors
│   ├── base.py          # Abstract base class
│   ├── pubmed.py        # PubMed via E-utilities
│   ├── semantic_scholar.py
│   ├── europepmc.py
│   ├── crossref.py
│   ├── openalex.py
│   └── enterprise/      # Optional (Scopus, WoS, Dimensions)
├── detection.py         # RCT detection logic
├── classification.py    # Topic classification
├── deduplication.py     # Cross-source deduplication
├── models.py            # RCTRecord dataclass
├── output.py            # Excel/CSV export
├── cli.py               # CLI argument parsing
└── main.py              # Orchestrator
```

## Examples

### Find cardiology RCTs only

```bash
python -m rct_finder --days 14 --query "cardiology OR cardiac OR heart" --output cardio_rcts.xlsx
```

### Use specific sources

```bash
python -m rct_finder --days 30 --sources pubmed europepmc --output pubmed_epmc.xlsx
```

### Include preprints

```bash
python -m rct_finder --days 7 --include-preprints --output with_preprints.xlsx
```

## Rate Limits

The tool respects API rate limits:

- **PubMed**: 10 req/sec with API key, 3 req/sec without
- **Semantic Scholar**: 10 req/sec (100 for partners)
- **Europe PMC**: 10 req/sec
- **Crossref**: 50 req/sec (polite pool)
- **OpenAlex**: 10 req/sec

## License

MIT License
