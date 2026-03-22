## MTH_9899_ML Project

This folder is a self-contained Python project for intraday feature engineering used in the Baruch MFE MTH 9899 course.

### Contents

- `feature_engineering.py` – core feature building utilities operating on daily and intraday CSV files.
- `main.py` – Entrypoint
- `train.ipynb` - Notebook used for research & that shows the code behind the analysis and plots
- `White_paper.pdf` - white paper on the research, tested features, models, model parameters, and the final model
- `final_model.pkl` - The trained model (best model was a Random Forest model)
- `random_forest_meta.json` - The metadata behind the final Random Forest model

### How to run the code

- Mode 1 - feature-generation
  `python main.py -i . -o output -s 20100104 -e 20151231 -m 1`
- Mode - run the saved ML model for prediction on the out-of-sample test dataset
  `python main.py -i output -o output_pred -s 20150101 -e 20151231 -p saved_models -m 2`

