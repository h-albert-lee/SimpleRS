from models.bert4rec import BERT4RecModel
from models.data_preparation import fetch_user_interaction_data, preprocess_data

def main():
    # 데이터 수집 및 전처리
    raw_data = fetch_user_interaction_data()
    data = preprocess_data(raw_data)  # {user_id: [embedding1, embedding2, ...], ...}

    # BERT4Rec 모델 초기화
    model = BERT4RecModel(embedding_dim=64, num_heads=4, num_layers=2, max_seq_length=50)

    # 모델 학습
    model.train(data)

    # 모델 저장
    model.save("path/to/save/bert4rec_model.pth")

if __name__ == "__main__":
    main()
