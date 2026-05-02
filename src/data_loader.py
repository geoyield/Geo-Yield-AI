import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
import logging

logger=logging.getLogger("adult-income")

# Column names
COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education-num", "marital-status",
    "occupation", "relationship", "race", "sex", "capital-gain", "capital-loss",
    "hours-per-week", "native-country", "income"
]

def load_data(train_path, test_path):
    logger.info("Loading training and tests datasets...")
    train_df = pd.read_csv(train_path, header=None, names=COLUMNS, na_values=" ?", skipinitialspace=True)
    test_df = pd.read_csv(test_path, header=0, names=COLUMNS, na_values=" ?", skipinitialspace=True, skiprows=1)
    test_df["income"] = test_df["income"].str.replace(".", "", regex=False)

    logger.info(f"Train shape: {train_df.shape}, Test shape: {test_df.shape}")
    logger.info(f"Missing values (train): {train_df.isnull().sum().sum()}, (tests): {test_df.isnull().sum().sum()}")
    return train_df.dropna(), test_df.dropna()

def preprocess_data(train_df, test_df):
    logger.info("Preprocessing and encoding features...")
    cat_cols = train_df.select_dtypes(include="object").columns.drop("income")
    label_encoders = {}

    for col in cat_cols:
        le = LabelEncoder()
        train_df[col] = le.fit_transform(train_df[col])
        test_df[col] = le.transform(test_df[col])
        label_encoders[col] = le

    train_df["income"] = train_df["income"].apply(lambda x: 1 if x == ">50K" else 0)
    test_df["income"] = test_df["income"].apply(lambda x: 1 if x == ">50K" else 0)

    X_train = train_df.drop("income", axis=1)
    y_train = train_df["income"]
    X_test = test_df.drop("income", axis=1)
    y_test = test_df["income"]

    scaler = StandardScaler()
    logger.info("Scaling features...")
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    logger.info(f"Feature columns: {list(X_train.columns)}")
    logger.info(f"X_train shape: {X_train_scaled.shape}, X_test shape: {X_test_scaled.shape}")
    return X_train_scaled, X_test_scaled, y_train.to_numpy(), y_test.to_numpy(), scaler, label_encoders