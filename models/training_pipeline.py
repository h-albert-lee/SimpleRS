from models.collaborative_filtering import CollaborativeFilteringModel
from models.bert4rec import BERT4RecModel
from models.data_preparation import fetch_user_interaction_data, preprocess_data

def main():
    # 데이터 수집 및 전처리
    raw_data = fetch_user_interaction_data()
    data = preprocess_data(raw_data)

    # 사용할 모델 선택 (예: Collaborative Filtering)
    model = CollaborativeFilteringModel(num_users=1000, num_items=1000, embedding_dim=50)

    # 모델 학습
    model.train(data)

    # 모델 저장
    model.save("path/to/save/model.pth")

if __name__ == "__main__":
    main()
