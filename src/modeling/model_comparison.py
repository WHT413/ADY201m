"""
This script implements a binary classification task to predict whether a player
will finish in the Top 4 (Win) or outside Top 4 (Loss) in TFT matches.
Two models are compared: Logistic Regression (baseline) and Random Forest Classifier.

Author: ADY201m Team
Date: March 2026
Course: Big Data Processing (ADY202)
================================================================================
"""

# ==============================================================================
# SECTION 1: IMPORT LIBRARIES
# ==============================================================================
import sqlite3
import pandas as pd
import numpy as np

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    roc_auc_score, 
    roc_curve,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score
)

import matplotlib.pyplot as plt
import seaborn as sns

# ==============================================================================
# SECTION 2: DATA LOADING AND PREPROCESSING
# ==============================================================================

def load_data_from_database(db_path: str) -> pd.DataFrame:
    """
    Load match data from SQLite database.
    
    Parameters:
        db_path (str): Path to the SQLite database file
    
    Returns:
        pd.DataFrame: DataFrame containing match data with columns:
                      puuid, match_id, placement, level, carry_name, 
                      carry_tier, carry_cost
    """
    # Establish connection to the database
    conn = sqlite3.connect(db_path)
    
    # Execute SQL query to extract relevant data from 'carries' table
    query = """
        SELECT 
            puuid, match_id, placement, level, 
            carry_name, carry_tier, carry_cost
        FROM carries
    """
    
    # Read data into pandas DataFrame
    df = pd.read_sql_query(query, conn)
    
    # Close database connection
    conn.close()
    
    print(f"[INFO] Data loaded successfully!")
    print(f"       Total records: {len(df)}")
    print(f"       Total matches: {df['match_id'].nunique()}")
    print(f"       Total players: {df['puuid'].nunique()}")
    
    return df


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess the raw data for model training.
    
    This function:
    1. Removes records with missing carry_cost values
    2. Creates a 'playstyle' feature based on carry cost
    3. Creates a binary target variable 'win' (1 = Top 4, 0 = Outside Top 4)
    4. Encodes playstyle as a binary feature
    
    Parameters:
        df (pd.DataFrame): Raw data from database
    
    Returns:
        pd.DataFrame: Preprocessed data with additional features
    """
    # Create a copy to avoid modifying original data
    data = df[df['carry_cost'].notna()].copy()
    
    # Create playstyle feature:
    # - FastLevel: Players who use expensive carries (cost > 3)
    #   Strategy: Level up quickly to access higher-cost champions
    # - Reroll: Players who use cheaper carries (cost <= 3)
    #   Strategy: Roll the shop multiple times to find 3-star units
    data['playstyle'] = data['carry_cost'].apply(
        lambda x: 'FastLevel' if x > 3 else 'Reroll'
    )
    
    # Create binary target variable
    # Win = 1 if placement <= 4 (Top 4 finish)
    # Loss = 0 if placement > 4 (Outside Top 4)
    data['win'] = (data['placement'] <= 4).astype(int)
    
    # One-hot encode playstyle feature
    # Convert categorical 'playstyle' to binary numeric feature
    data['is_fastlevel'] = (data['playstyle'] == 'FastLevel').astype(int)
    
    print(f"[INFO] Data preprocessing completed!")
    print(f"       Records after removing NaN: {len(data)}")
    print(f"       Win distribution: {data['win'].value_counts().to_dict()}")
    print(f"       Playstyle distribution: {data['playstyle'].value_counts().to_dict()}")
    
    return data


# ==============================================================================
# SECTION 3: MODEL DEFINITION AND TRAINING
# ==============================================================================

def train_logistic_regression(X_train: np.ndarray, y_train: np.ndarray) -> LogisticRegression:
    """
    Train a Logistic Regression classifier.
    
    Logistic Regression is a linear classification algorithm that models the
    probability of the binary outcome using a logistic (sigmoid) function.
    
    Parameters:
        X_train (np.ndarray): Training features (scaled)
        y_train (np.ndarray): Training labels (binary: 0 or 1)
    
    Returns:
        LogisticRegression: Trained model
    """
    # Initialize Logistic Regression model
    # max_iter=1000: Maximum iterations for solver convergence
    # random_state=42: Ensures reproducibility of results
    model = LogisticRegression(max_iter=1000, random_state=42)
    
    # Fit the model to training data
    model.fit(X_train, y_train)
    
    print("[INFO] Logistic Regression model trained successfully!")
    
    return model


def train_random_forest(X_train: np.ndarray, y_train: np.ndarray) -> RandomForestClassifier:
    """
    Train a Random Forest Classifier.
    
    Random Forest is an ensemble learning method that constructs multiple
    decision trees during training and outputs the mode of their predictions.
    
    Parameters:
        X_train (np.ndarray): Training features
        y_train (np.ndarray): Training labels (binary: 0 or 1)
    
    Returns:
        RandomForestClassifier: Trained model
    """
    # Initialize Random Forest Classifier
    # n_estimators=100: Number of trees in the forest
    # max_depth=10: Maximum depth of each tree (prevents overfitting)
    # random_state=42: Ensures reproducibility
    # n_jobs=-1: Use all available CPU cores for parallel processing
    # class_weight='balanced': Automatically adjust weights inversely proportional
    #                          to class frequencies (handles class imbalance)
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'
    )
    
    # Fit the model to training data
    model.fit(X_train, y_train)
    
    print("[INFO] Random Forest model trained successfully!")
    
    return model


# ==============================================================================
# SECTION 4: MODEL EVALUATION
# ==============================================================================

def evaluate_model(
    model_name: str,
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    needs_proba: bool = True
) -> dict:
    """
    Evaluate a classification model using multiple metrics.
    
    Parameters:
        model_name (str): Name of the model for reporting
        model: Trained sklearn model
        X_test (np.ndarray): Test features
        y_test (np.ndarray): Test labels
        needs_proba (bool): Whether to calculate probability-based metrics
    
    Returns:
        dict: Dictionary containing evaluation metrics
    """
    # Generate predictions
    y_pred = model.predict(X_test)
    
    # Initialize results dictionary
    results = {
        'name': model_name,
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1_score': f1_score(y_test, y_pred),
        'confusion_matrix': confusion_matrix(y_test, y_pred)
    }
    
    # Calculate probability-based metrics if needed
    if needs_proba:
        y_prob = model.predict_proba(X_test)[:, 1]
        results['auc_roc'] = roc_auc_score(y_test, y_prob)
        results['y_prob'] = y_prob
    
    # Print results
    print("=" * 50)
    print(f"{model_name.upper()} RESULTS")
    print("=" * 50)
    print(f"Accuracy:  {results['accuracy']:.4f}")
    print(f"Precision: {results['precision']:.4f}")
    print(f"Recall:    {results['recall']:.4f}")
    print(f"F1-Score:  {results['f1_score']:.4f}")
    
    if needs_proba:
        print(f"AUC-ROC:   {results['auc_roc']:.4f}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Loss', 'Win']))
    
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print()
    
    return results


# ==============================================================================
# SECTION 5: VISUALIZATION
# ==============================================================================

def plot_feature_importance(rf_model: RandomForestClassifier, feature_names: list) -> None:
    """
    Plot feature importance from Random Forest model.
    
    Random Forest provides built-in feature importance based on the mean
    decrease in impurity (Gini importance) when a feature is used for splitting.
    
    Parameters:
        rf_model (RandomForestClassifier): Trained Random Forest model
        feature_names (list): Names of the features
    """
    # Get feature importances
    importances = rf_model.feature_importances_
    
    # Create DataFrame for easier plotting
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    }).sort_values('importance', ascending=True)
    
    # Create horizontal bar chart
    plt.figure(figsize=(10, 6))
    plt.barh(importance_df['feature'], importance_df['importance'], color='steelblue')
    plt.xlabel('Feature Importance (Mean Decrease in Impurity)', fontsize=12)
    plt.title('Random Forest Feature Importance', fontsize=14)
    plt.tight_layout()
    plt.savefig('reports/imgs/feature_importance.png', dpi=150, bbox_inches='tight')
    plt.show()
    
    print("\nFeature Importance (Random Forest):")
    for feat, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
        print(f"  {feat}: {imp:.4f}")


def plot_confusion_matrix_comparison(
    logreg_cm: np.ndarray,
    rf_cm: np.ndarray,
    save_path: str = 'confusion_matrices.png'
) -> None:
    """
    Plot side-by-side confusion matrices for both models.
    
    Parameters:
        logreg_cm (np.ndarray): Confusion matrix from Logistic Regression
        rf_cm (np.ndarray): Confusion matrix from Random Forest
        save_path (str): Path to save the figure
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot Logistic Regression confusion matrix
    sns.heatmap(
        logreg_cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=['Predicted Loss', 'Predicted Win'],
        yticklabels=['Actual Loss', 'Actual Win'],
        ax=axes[0]
    )
    axes[0].set_title('Logistic Regression', fontsize=12)
    
    # Plot Random Forest confusion matrix
    sns.heatmap(
        rf_cm, annot=True, fmt='d', cmap='Greens',
        xticklabels=['Predicted Loss', 'Predicted Win'],
        yticklabels=['Actual Loss', 'Actual Win'],
        ax=axes[1]
    )
    axes[1].set_title('Random Forest', fontsize=12)
    
    plt.tight_layout()
    plt.savefig('reports/imgs/confusion_matrices.png', dpi=150, bbox_inches='tight')
    plt.show()
    
    print(f"[INFO] Confusion matrices saved to: reports/imgs/confusion_matrices.png")


# ==============================================================================
# SECTION 6: PLAYSTYLE ANALYSIS
# ==============================================================================

def analyze_playstyle(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze win rates by playstyle (FastLevel vs Reroll).
    
    This analysis helps understand which strategy is more effective.
    
    Parameters:
        df (pd.DataFrame): Original data with playstyle column
    
    Returns:
        pd.DataFrame: Summary statistics by playstyle
    """
    # Filter data with valid carry_cost
    valid_data = df[df['carry_cost'].notna()].copy()
    
    # Group by playstyle and calculate statistics
    playstyle_analysis = valid_data.groupby('playstyle').agg({
        'placement': [
            ('total_games', 'count'),
            ('wins', lambda x: (x <= 4).sum())
        ]
    })
    
    # Flatten column names
    playstyle_analysis.columns = ['total_games', 'wins']
    
    # Calculate win rate
    playstyle_analysis['win_rate'] = (
        playstyle_analysis['wins'] / playstyle_analysis['total_games'] * 100
    )
    
    # Round for display
    playstyle_analysis = playstyle_analysis.round(2)
    
    print("=" * 50)
    print("PLAYSTYLE ANALYSIS")
    print("=" * 50)
    print(playstyle_analysis.to_string())
    print()
    
    return playstyle_analysis


# ==============================================================================
# SECTION 7: MAIN EXECUTION
# ==============================================================================

def main():
    """
    Main function to execute the complete analysis pipeline.
    """
    print("=" * 70)
    print("TASK 2: LOGISTIC REGRESSION vs RANDOM FOREST CLASSIFIER")
    print("TFT Match Outcome Prediction")
    print("=" * 70)
    print()
    
    # Step 1: Load data from database
    print("[STEP 1] Loading data from database...")
    df = load_data_from_database('data/processed/tft_data.db')
    print()
    
    # Step 2: Preprocess data
    print("[STEP 2] Preprocessing data...")
    data = preprocess_data(df)
    print()
    
    # Step 3: Prepare features and target
    print("[STEP 3] Preparing features and target...")
    feature_cols = ['carry_cost', 'level', 'carry_tier', 'is_fastlevel']
    X = data[feature_cols].values
    y = data['win'].values
    
    # Split data into training (80%) and testing (20%) sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"       Training set size: {len(X_train)}")
    print(f"       Testing set size: {len(X_test)}")
    print()
    
    # Step 4: Scale features for Logistic Regression
    # StandardScaler transforms features to have mean=0 and std=1
    # This is important for Logistic Regression convergence
    print("[STEP 4] Scaling features for Logistic Regression...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    print()
    
    # Step 5: Train models
    print("[STEP 5] Training models...")
    print("-" * 50)
    
    # Train Logistic Regression (requires scaled data)
    logreg_model = train_logistic_regression(X_train_scaled, y_train)
    
    # Train Random Forest (does not require scaling)
    rf_model = train_random_forest(X_train, y_train)
    print()
    
    # Step 6: Evaluate models
    print("[STEP 6] Evaluating models...")
    print("-" * 50)
    
    logreg_results = evaluate_model(
        "Logistic Regression",
        logreg_model,
        X_test_scaled,
        y_test
    )
    
    rf_results = evaluate_model(
        "Random Forest",
        rf_model,
        X_test,
        y_test
    )
    
    # Step 7: Compare models
    print("[STEP 7] Model Comparison Summary")
    print("-" * 50)
    comparison = pd.DataFrame({
        'Model': ['Logistic Regression', 'Random Forest'],
        'Accuracy': [logreg_results['accuracy'], rf_results['accuracy']],
        'Precision': [logreg_results['precision'], rf_results['precision']],
        'Recall': [logreg_results['recall'], rf_results['recall']],
        'F1-Score': [logreg_results['f1_score'], rf_results['f1_score']],
        'AUC-ROC': [logreg_results['auc_roc'], rf_results['auc_roc']]
    })
    print(comparison.to_string(index=False))
    print()
    
    # Step 8: Visualizations
    print("[STEP 8] Generating visualizations...")
    plot_feature_importance(rf_model, feature_cols)
    plot_confusion_matrix_comparison(
        logreg_results['confusion_matrix'],
        rf_results['confusion_matrix']
    )
    
    # Step 9: Playstyle Analysis
    print("[STEP 9] Playstyle Analysis")
    print("-" * 50)
    analyze_playstyle(data)
    
    # Step 10: Hypothesis Testing Conclusion
    print("=" * 70)
    print("HYPOTHESIS TESTING CONCLUSION")
    print("=" * 70)
    print()
    print("Null Hypothesis (H₀): Random Forest does NOT perform better than")
    print("                      Logistic Regression for TFT outcome prediction")
    print()
    print("Alternative Hypothesis (H₁): Random Forest performs BETTER than")
    print("                             Logistic Regression for TFT outcome prediction")
    print()
    
    # Decision based on AUC-ROC (primary metric for imbalanced classification)
    if rf_results['auc_roc'] > logreg_results['auc_roc']:
        auc_improvement = (rf_results['auc_roc'] - logreg_results['auc_roc']) * 100
        print(f"DECISION: REJECT H₀")
        print(f"          Random Forest shows {auc_improvement:.2f}% improvement in AUC-ROC")
        print(f"          over Logistic Regression.")
    else:
        print(f"DECISION: FAIL TO REJECT H₀")
        print(f"          Logistic Regression performs equally well or better.")
        print(f"          Following Occam's Razor, we prefer the simpler model.")
    
    print()
    print("=" * 70)
    print("ANALYSIS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()