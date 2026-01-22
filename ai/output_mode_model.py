import numpy as np
from sklearn.linear_model import LogisticRegression
from ai.labels import LABELS
from ai.synthetic_profiles import generate_profiles

FEATURE_KEYS = [
    "A1","A2","A3","A4","A5",
    "I1","I2","I3","I4","I5","I6",
    "T1","T2","T3","T4","T5","T6",
    "V1","V2","V3","V4","V5","V6",
    "W1","W2","W3","W4"
]

OUTPUT_MODE_TO_ID = {
    "research": 0,
    "application": 1,
    "advisory": 2,
    "teaching": 3,
    "execution": 4
}

ID_TO_OUTPUT_MODE = {v: k for k, v in OUTPUT_MODE_TO_ID.items()}


def build_xy(data):
    X, y = [], []

    for prof in data:
        persona = prof["persona"]
        label = LABELS[persona]["output_mode"]

        X.append([prof["answers"][k] for k in FEATURE_KEYS])
        y.append(OUTPUT_MODE_TO_ID[label])

    return np.array(X), np.array(y)


def train_model(X, y):
    model = LogisticRegression(
        solver="lbfgs",
        max_iter=1000
    )
    model.fit(X, y)
    return model


def predict_output_mode(model, answers):
    print('Prediction: ', answers)
    x = np.array([[answers.get(k, 3) for k in FEATURE_KEYS]])
    probabilities = model.predict_proba(x)[0]

    return {
        ID_TO_OUTPUT_MODE[i]: float(probabilities[i])
        for i in range(len(probabilities))
    }


if __name__ == "__main__":
    dataset = generate_profiles(lazy=True)
    X_, y_ = build_xy(dataset)
    model_ = train_model(X_, y_)

    for profile in dataset:
        probs = predict_output_mode(model_, profile["answers"])
        print(profile["persona"])
        print("Expected:", LABELS[profile["persona"]]["output_mode"])
        print("Predicted:", probs)
        print("-" * 40)
