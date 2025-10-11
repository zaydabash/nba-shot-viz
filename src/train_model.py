"""
NBA Shot Prediction Model Training

This module trains machine learning models to predict shot success probability
based on historical NBA shot chart data.
"""

from __future__ import annotations
import os
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
import joblib

# Optional LightGBM import
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("Warning: LightGBM not available. Only Logistic Regression will be trained.")

from .util import ensure_dirs, csv_path_for


def load_training_data(players: List[str], seasons: List[str], season_types: List[str]) -> pd.DataFrame:
    """
    Load shot chart data from multiple players/seasons for training.
    
    Args:
        players: List of player names
        seasons: List of seasons (e.g., ['2023-24', '2022-23'])
        season_types: List of season types (e.g., ['Regular Season'])
    
    Returns:
        Combined DataFrame with all shot data
    """
    all_data = []
    
    for player in players:
        for season in seasons:
            for season_type in season_types:
                csv_path = csv_path_for(player, season, season_type)
                if Path(csv_path).exists() and Path(csv_path).stat().st_size > 0:
                    try:
                        df = pd.read_csv(csv_path)
                        if len(df) > 0:
                            df['player'] = player
                            df['season'] = season
                            df['season_type'] = season_type
                            all_data.append(df)
                            print(f"Loaded {len(df)} shots for {player} {season} {season_type}")
                    except Exception as e:
                        print(f"Error loading {csv_path}: {e}")
    
    if not all_data:
        raise ValueError("No training data found. Please ensure shot data exists.")
    
    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"Total training data: {len(combined_df)} shots from {len(players)} players")
    return combined_df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create ML features from raw shot chart data.
    
    Args:
        df: Raw shot chart DataFrame
    
    Returns:
        DataFrame with engineered features
    """
    df = df.copy()
    
    # Basic shot features
    df['shot_distance'] = np.sqrt(df['LOC_X']**2 + df['LOC_Y']**2)
    df['shot_angle'] = np.arctan2(df['LOC_Y'], df['LOC_X']) * 180 / np.pi
    
    # Court zones (simplified)
    df['is_paint'] = (df['LOC_X'].abs() <= 80) & (df['LOC_Y'] <= 190)
    df['is_corner_3'] = (df['LOC_X'].abs() >= 220) & (df['LOC_Y'] <= 140)
    df['is_above_break_3'] = (df['shot_distance'] >= 237.5) & (~df['is_corner_3'])
    df['is_midrange'] = (~df['is_paint']) & (~df['is_corner_3']) & (~df['is_above_break_3'])
    
    # Time-based features (if available)
    if 'PERIOD' in df.columns:
        df['is_late_game'] = df['PERIOD'] >= 4
        df['is_overtime'] = df['PERIOD'] > 4
    else:
        df['is_late_game'] = False
        df['is_overtime'] = False
    
    # Shot clock features (if available)
    if 'SHOT_CLOCK' in df.columns:
        df['shot_clock_low'] = df['SHOT_CLOCK'] <= 5
        df['shot_clock_high'] = df['SHOT_CLOCK'] >= 20
    else:
        df['shot_clock_low'] = False
        df['shot_clock_high'] = False
    
    # Player-specific features
    df['player_encoded'] = df['player'].astype('category').cat.codes
    
    return df


def prepare_training_data(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Prepare features and target for model training.
    
    Args:
        df: DataFrame with engineered features
    
    Returns:
        X: Feature matrix
        y: Target vector (shot made flag)
        feature_names: List of feature names
    """
    # Define feature columns
    feature_cols = [
        'LOC_X', 'LOC_Y', 'shot_distance', 'shot_angle',
        'is_paint', 'is_corner_3', 'is_above_break_3', 'is_midrange',
        'is_late_game', 'is_overtime', 'shot_clock_low', 'shot_clock_high',
        'player_encoded'
    ]
    
    # Filter to available columns
    available_cols = [col for col in feature_cols if col in df.columns]
    
    # Prepare features
    X = df[available_cols].values
    y = df['SHOT_MADE_FLAG'].values
    
    # Handle missing values
    X = np.nan_to_num(X, nan=0.0)
    
    return X, y, available_cols


def train_logistic_regression(X: np.ndarray, y: np.ndarray) -> Tuple[LogisticRegression, StandardScaler]:
    """
    Train a logistic regression model.
    
    Args:
        X: Feature matrix
        y: Target vector
    
    Returns:
        Trained model and scaler
    """
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    print(f"Logistic Regression - Accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print(f"Logistic Regression - ROC AUC: {roc_auc_score(y_test, y_pred_proba):.3f}")
    
    return model, scaler


def train_lightgbm(X: np.ndarray, y: np.ndarray) -> Optional[lgb.LGBMClassifier]:
    """
    Train a LightGBM model.
    
    Args:
        X: Feature matrix
        y: Target vector
    
    Returns:
        Trained LightGBM model or None if not available
    """
    if not LIGHTGBM_AVAILABLE:
        print("LightGBM not available. Skipping LightGBM training.")
        return None
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    model = lgb.LGBMClassifier(
        random_state=42,
        n_estimators=100,
        learning_rate=0.1,
        max_depth=6,
        num_leaves=31,
        verbose=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    print(f"LightGBM - Accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print(f"LightGBM - ROC AUC: {roc_auc_score(y_test, y_pred_proba):.3f}")
    
    return model


def save_model(model, scaler: Optional[StandardScaler], feature_names: List[str], 
               model_name: str, model_type: str) -> str:
    """
    Save trained model and metadata.
    
    Args:
        model: Trained model
        scaler: Feature scaler (if applicable)
        feature_names: List of feature names
        model_name: Name for the model
        model_type: Type of model ('logistic' or 'lightgbm')
    
    Returns:
        Path to saved model file
    """
    ensure_dirs("models")
    
    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names,
        'model_type': model_type,
        'model_name': model_name
    }
    
    model_path = f"models/{model_name}_{model_type}.pkl"
    joblib.dump(model_data, model_path)
    
    print(f"Model saved to: {model_path}")
    return model_path


def train_models(players: Optional[List[str]] = None, 
                seasons: Optional[List[str]] = None,
                season_types: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Train both logistic regression and LightGBM models.
    
    Args:
        players: List of players to train on (default: popular players)
        seasons: List of seasons (default: recent seasons)
        season_types: List of season types (default: Regular Season)
    
    Returns:
        Dictionary mapping model types to file paths
    """
    # Default training data
    if players is None:
        players = ["Stephen Curry", "LeBron James", "Kevin Durant", "Giannis Antetokounmpo", 
                  "Luka Doncic", "Jayson Tatum", "Joel Embiid", "Nikola Jokic"]
    
    if seasons is None:
        seasons = ["2023-24", "2022-23", "2021-22"]
    
    if season_types is None:
        season_types = ["Regular Season"]
    
    print("Loading training data...")
    df = load_training_data(players, seasons, season_types)
    
    print("Creating features...")
    df_features = create_features(df)
    
    print("Preparing training data...")
    X, y, feature_names = prepare_training_data(df_features)
    
    print(f"Training on {len(X)} samples with {len(feature_names)} features")
    print(f"Features: {feature_names}")
    
    # Train models
    print("\nTraining Logistic Regression...")
    lr_model, lr_scaler = train_logistic_regression(X, y)
    
    # Save logistic regression model
    print("\nSaving Logistic Regression model...")
    lr_path = save_model(lr_model, lr_scaler, feature_names, "shot_prediction", "logistic")
    
    result = {'logistic': lr_path}
    
    # Train LightGBM if available
    if LIGHTGBM_AVAILABLE:
        print("\nTraining LightGBM...")
        lgb_model = train_lightgbm(X, y)
        if lgb_model is not None:
            print("\nSaving LightGBM model...")
            lgb_path = save_model(lgb_model, None, feature_names, "shot_prediction", "lightgbm")
            result['lightgbm'] = lgb_path
    else:
        print("\nSkipping LightGBM training (not available)")
    
    return result


def main():
    """CLI entry point for model training."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Train NBA shot prediction models")
    parser.add_argument("--players", nargs="+", help="Players to train on")
    parser.add_argument("--seasons", nargs="+", help="Seasons to train on")
    parser.add_argument("--season-types", nargs="+", help="Season types to train on")
    
    args = parser.parse_args()
    
    try:
        model_paths = train_models(
            players=args.players,
            seasons=args.seasons,
            season_types=args.season_types
        )
        print(f"\nTraining complete! Models saved:")
        for model_type, path in model_paths.items():
            print(f"  {model_type}: {path}")
    except Exception as e:
        print(f"Training failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
