# Notebooks Overview

This directory contains Jupyter notebooks for exploring and analyzing the Yelp food datasets.

## Notebooks

### 01_data_exploration.ipynb
**Quick Dataset Overview (Original 4 datasets)**

Explores archive_2, archive_3, archive_6, and onlinefoods.csv

### 01_data_exploration_extended.ipynb ⭐
**Comprehensive TF-IDF + UGC Suitability Assessment**

Evaluates ALL datasets from `/data`:
- **archive_2**: Food.com recipes and user interactions
- **archive_3**: Recipe reviews dataset  
- **archive_4**: Yelp academic dataset (business, reviews, tips, users)
- **archive_6**: Food coding dataset
- **onlinefoods.csv**: Online food orders
- **OpenFoodFacts**: Global food products database

**What it does:**
- Loads and analyzes all 6 datasets
- Evaluates each dataset for TF-IDF + UGC suitability
- Provides detailed assessment with star ratings
- **Recommends Archive_4 (Yelp) as BEST for content-based recommendation**
- Shows implementation priority roadmap

**Run it By using vscode jupyter support.**

## Quick Start

1. **Install dependencies** (if not already installed):
```bash
pip install jupyter pandas numpy matplotlib seaborn pyarrow
```

## Dataset Structure

```
data/
├── archive_2/
│   ├── PP_recipes.csv          # Preprocessed recipes
│   ├── PP_users.csv            # User data
│   ├── interactions_train.csv  # User-recipe interactions
│   ├── interactions_test.csv
│   └── interactions_validation.csv
├── archive_3/
│   ├── recipes.csv/.parquet    # Recipe data
│   └── reviews.csv/.parquet    # User reviews
├── archive_4/                  # ⭐ Yelp Academic Dataset (JSON)
│   ├── yelp_academic_dataset_business.json  # Business metadata
│   ├── yelp_academic_dataset_review.json    # UGC reviews
│   ├── yelp_academic_dataset_tip.json       # Short UGC tips
│   └── yelp_academic_dataset_user.json      # User profiles
├── archive_6/
│   └── food_coded.csv          # Food preference coding
├── onlinefoods.csv             # Online food orders
└── en.openfoodfacts.org.products.tsv  # Global food products DB
```

## Next Steps for TF-IDF

After exploring with `01_data_exploration_extended.ipynb`, the recommended approach:

### 🏆 Phase 1: Archive_4 (Yelp) - RECOMMENDED
Focus on Yelp dataset due to:
- Rich UGC (user-generated content): reviews + tips
- Business metadata: categories, attributes
- Large scale with food-specific filtering

**Workflow:**
1. **Text Preprocessing**
   - Clean review text (remove HTML, special chars)
   - Tokenization and lemmatization
   - Remove stop words

2. **TF-IDF Vectorization**
   - Apply TF-IDF to review text
   - Business category encoding
   - Combine content features

3. **Content-Based Filtering**
   - Calculate cosine similarity
   - Build recommendation engine
   - Incorporate sentiment analysis

4. **Evaluation**
   - Test with sample businesses
   - Measure recommendation quality
   - Compare with collaborative filtering

### Phase 2: Archive_3 (Recipe Reviews)
Hybrid approach combining recipe content + UGC sentiment

### Phase 3: Archive_2 (Food.com)
Pure content-based on ingredients/tags

## Tips

- **Large datasets**: Some datasets (especially archive_3 reviews) may be large. Use `.head()` or sampling for initial exploration
- **Parquet files**: Use `pd.read_parquet()` for faster loading when available
- **Memory**: If you encounter memory issues, process datasets one at a time
- **Text columns**: Focus on columns like `name`, `ingredients`, `tags`, `description` for TF-IDF
