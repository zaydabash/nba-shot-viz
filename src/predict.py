"""
NBA Shot Prediction Inference

This module provides shot probability prediction using trained ML models.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import joblib

from .util import ensure_dirs


def load_model(model_path: str) -> Dict:
    """
    Load a trained model and its metadata.
    
    Args:
        model_path: Path to the saved model file
    
    Returns:
        Dictionary containing model, scaler, feature_names, etc.
    """
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    model_data = joblib.load(model_path)
    return model_data


def get_available_models() -> Dict[str, str]:
    """
    Get list of available trained models.
    
    Returns:
        Dictionary mapping model types to file paths
    """
    models_dir = Path("models")
    if not models_dir.exists():
        return {}
    
    available_models = {}
    for model_file in models_dir.glob("*.pkl"):
        if "logistic" in model_file.name:
            available_models["logistic"] = str(model_file)
        elif "lightgbm" in model_file.name:
            available_models["lightgbm"] = str(model_file)
    
    return available_models


def create_features_for_prediction(df: pd.DataFrame, player_name: str) -> pd.DataFrame:
    """
    Create ML features for prediction from shot chart data.
    
    Args:
        df: Raw shot chart DataFrame
        player_name: Name of the player
    
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
    
    # Player-specific features (simple encoding)
    df['player_encoded'] = hash(player_name) % 1000  # Simple hash-based encoding
    
    return df


def predict_shot_probabilities(df: pd.DataFrame, player_name: str, 
                             model_type: str = "lightgbm") -> np.ndarray:
    """
    Predict shot success probabilities for all shots in the DataFrame.
    
    Args:
        df: Shot chart DataFrame
        player_name: Name of the player
        model_type: Type of model to use ('logistic' or 'lightgbm')
    
    Returns:
        Array of shot success probabilities
    """
    # Get available models
    available_models = get_available_models()
    
    if not available_models:
        raise ValueError("No trained models found. Please train models first.")
    
    if model_type not in available_models:
        # Fallback to available model
        model_type = list(available_models.keys())[0]
        print(f"Model type '{model_type}' not found. Using '{model_type}' instead.")
    
    # Load model
    model_data = load_model(available_models[model_type])
    model = model_data['model']
    scaler = model_data.get('scaler')
    feature_names = model_data['feature_names']
    
    # Create features
    df_features = create_features_for_prediction(df, player_name)
    
    # Prepare features
    X = df_features[feature_names].values
    X = np.nan_to_num(X, nan=0.0)
    
    # Scale features if scaler is available
    if scaler is not None:
        X = scaler.transform(X)
    
    # Predict probabilities
    if hasattr(model, 'predict_proba'):
        probabilities = model.predict_proba(X)[:, 1]
    else:
        # Fallback for models without predict_proba
        predictions = model.predict(X)
        probabilities = predictions.astype(float)
    
    return probabilities


def predict_for_visualization(df: pd.DataFrame, player_name: str, 
                            model_type: str = "lightgbm") -> pd.DataFrame:
    """
    Add prediction probabilities to DataFrame for visualization.
    
    Args:
        df: Shot chart DataFrame
        player_name: Name of the player
        model_type: Type of model to use
    
    Returns:
        DataFrame with added prediction columns
    """
    df_result = df.copy()
    
    try:
        # Get predictions
        probabilities = predict_shot_probabilities(df, player_name, model_type)
        
        # Add prediction columns
        df_result['predicted_probability'] = probabilities
        df_result['predicted_made'] = probabilities > 0.5
        df_result['prediction_confidence'] = np.abs(probabilities - 0.5) * 2
        
        # Add prediction accuracy (if we have actual results)
        if 'SHOT_MADE_FLAG' in df.columns:
            df_result['prediction_correct'] = (df_result['predicted_made'] == df_result['SHOT_MADE_FLAG'])
            df_result['prediction_error'] = np.abs(df_result['predicted_probability'] - df_result['SHOT_MADE_FLAG'])
        
    except Exception as e:
        print(f"Prediction failed: {e}")
        # Add default values
        df_result['predicted_probability'] = 0.5
        df_result['predicted_made'] = False
        df_result['prediction_confidence'] = 0.0
        if 'SHOT_MADE_FLAG' in df.columns:
            df_result['prediction_correct'] = False
            df_result['prediction_error'] = 0.5
    
    return df_result


def get_model_performance(df: pd.DataFrame, player_name: str, 
                         model_type: str = "lightgbm") -> Dict[str, float]:
    """
    Calculate model performance metrics.
    
    Args:
        df: Shot chart DataFrame with predictions
        player_name: Name of the player
        model_type: Type of model to use
    
    Returns:
        Dictionary of performance metrics
    """
    if 'SHOT_MADE_FLAG' not in df.columns:
        return {"error": "No actual shot results available"}
    
    try:
        df_with_pred = predict_for_visualization(df, player_name, model_type)
        
        # Calculate metrics
        accuracy = df_with_pred['prediction_correct'].mean()
        mae = df_with_pred['prediction_error'].mean()
        
        # ROC AUC (if we have probabilities)
        if 'predicted_probability' in df_with_pred.columns:
            from sklearn.metrics import roc_auc_score
            try:
                roc_auc = roc_auc_score(df_with_pred['SHOT_MADE_FLAG'], df_with_pred['predicted_probability'])
            except ValueError:
                roc_auc = 0.5  # Fallback for edge cases
        else:
            roc_auc = 0.5
        
        return {
            "accuracy": accuracy,
            "mae": mae,
            "roc_auc": roc_auc,
            "total_shots": len(df_with_pred)
        }
    
    except Exception as e:
        return {"error": f"Performance calculation failed: {e}"}


def main():
    """CLI entry point for prediction."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Predict NBA shot probabilities")
    parser.add_argument("--player", required=True, help="Player name")
    parser.add_argument("--season", required=True, help="Season")
    parser.add_argument("--season-type", required=True, help="Season type")
    parser.add_argument("--model-type", default="lightgbm", choices=["logistic", "lightgbm"],
                       help="Model type to use")
    parser.add_argument("--csv-path", help="Path to CSV file (optional)")
    
    args = parser.parse_args()
    
    try:
        # Load data
        if args.csv_path:
            df = pd.read_csv(args.csv_path)
        else:
            from .util import csv_path_for
            csv_path = csv_path_for(args.player, args.season, args.season_type)
            if not Path(csv_path).exists():
                print(f"No data found for {args.player} {args.season} {args.season_type}")
                return 1
            df = pd.read_csv(csv_path)
        
        # Make predictions
        df_with_pred = predict_for_visualization(df, args.player, args.model_type)
        
        # Show results
        print(f"Predictions for {args.player} ({args.season} {args.season_type})")
        print(f"Total shots: {len(df_with_pred)}")
        
        if 'predicted_probability' in df_with_pred.columns:
            print(f"Average predicted probability: {df_with_pred['predicted_probability'].mean():.3f}")
            print(f"Predicted makes: {df_with_pred['predicted_made'].sum()}")
        
        # Show performance if we have actual results
        if 'SHOT_MADE_FLAG' in df.columns:
            performance = get_model_performance(df, args.player, args.model_type)
            if "error" not in performance:
                print(f"Model accuracy: {performance['accuracy']:.3f}")
                print(f"Mean absolute error: {performance['mae']:.3f}")
                print(f"ROC AUC: {performance['roc_auc']:.3f}")
        
        # Save results
        output_path = f"outputs/predictions/{args.player}_{args.season}_{args.season_type}_{args.model_type}.csv"
        ensure_dirs("outputs/predictions")
        df_with_pred.to_csv(output_path, index=False)
        print(f"Results saved to: {output_path}")
        
    except Exception as e:
        print(f"Prediction failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
