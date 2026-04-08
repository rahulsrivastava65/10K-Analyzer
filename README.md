# 10K Summary

`10K Summary` is a Streamlit-based Form 10-K analyzer that pulls SEC annual filings, extracts structured metrics and narrative sections, and assembles an executive-ready one-page summary with exports to Excel, PDF, and PowerPoint.

## Run locally

```cmd
cd /d "C:\Users\rahul\Downloads\FPNA Project"
python -m streamlit run app.py
```

## Publish on Streamlit Community Cloud

1. Put this project in a GitHub repository.
2. Make sure the app entrypoint is `app.py`.
3. Keep `requirements.txt` in the repo root.
4. In Streamlit Community Cloud, create a new app and point it to this repository.
5. Select:
   - Branch: your publish branch
   - Main file path: `app.py`
6. Deploy the app.

Official deployment reference:
- [Deploy your app on Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)

## Notes

- SEC and market-data access depend on runtime network connectivity.
- Cached SEC downloads are stored locally in `sec-edgar-filings/` and are excluded from source control.
- Review all outputs against primary filings before external use.
