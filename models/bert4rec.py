import torch
import torch.nn as nn
import numpy as np
from typing import Any, List
from models.base_model import BaseModel

class TransformerEncoder(nn.Module):
    def __init__(self, embedding_dim: int = 64, num_heads: int = 4, num_layers: int = 4, max_seq_length: int = 50):
        super(TransformerEncoder, self).__init__()
        self.embedding_dim = embedding_dim
        self.position_embedding = nn.Embedding(max_seq_length, embedding_dim)
        encoder_layer = nn.TransformerEncoderLayer(d_model=embedding_dim, nhead=num_heads)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        # 출력층은 다음 임베딩 예측을 위해 구성
        self.output_layer = nn.Linear(embedding_dim, embedding_dim)

    def forward(self, input_seq):
        """
        input_seq: (batch_size, seq_length, embedding_dim)
        """
        batch_size, seq_length, _ = input_seq.size()
        positions = torch.arange(seq_length, device=input_seq.device).unsqueeze(0).expand(batch_size, seq_length)
        pos_embed = self.position_embedding(positions)
        # 입력 임베딩에 위치 임베딩 추가
        embeddings = input_seq + pos_embed

        # Transformer는 (seq_length, batch_size, embedding_dim) 형식을 요구
        embeddings = embeddings.permute(1, 0, 2)
        transformer_out = self.transformer_encoder(embeddings)
        transformer_out = transformer_out.permute(1, 0, 2)  # (batch_size, seq_length, embedding_dim)

        # 마지막 타임스텝에 대해 예측
        output = self.output_layer(transformer_out[:, -1, :])
        return output  # (batch_size, embedding_dim)

class BERT4RecModel(BaseModel):
    def __init__(self, embedding_dim: int = 64, num_heads: int = 4, num_layers: int = 2, max_seq_length: int = 50):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = TransformerEncoder(embedding_dim, num_heads, num_layers, max_seq_length).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()  # 임베딩 예측을 위한 MSE 손실 사용

    def train(self, data: Any) -> None:
        """
        data: {user_id: [embedding1, embedding2, ..., embeddingT], ...}
        각 사용자 시퀀스를 학습 샘플로 사용.
        """
        self.model.train()
        epochs = 5
        for epoch in range(epochs):
            total_loss = 0.0
            for user_id, sequence in data.items():
                # 시퀀스를 텐서로 변환하고 배치 차원 추가
                seq_tensor = torch.tensor(sequence, dtype=torch.float, device=self.device).unsqueeze(0)  # shape: (1, T, embedding_dim)
                
                # 예측 목표: 시퀀스의 마지막 아이템(embedding)
                target = seq_tensor[:, -1, :]  # shape: (1, embedding_dim)
                
                # 입력 시퀀스: 마지막 아이템을 제외한 시퀀스
                input_seq = seq_tensor[:, :-1, :]  # shape: (1, T-1, embedding_dim)
                
                self.optimizer.zero_grad()
                output = self.model(input_seq)  # shape: (1, embedding_dim)
                loss = self.criterion(output, target)
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
            print(f"Epoch {epoch+1}, Loss: {total_loss}")

    def predict(self, user_id: str, candidate_embeddings: List[np.ndarray]) -> List[Any]:
        """
        사용자에 대한 추천 점수를 예측.
        candidate_embeddings: 추천 후보 콘텐츠들의 임베딩 리스트
        """
        self.model.eval()
        # 더미 시퀀스를 사용하여 다음 임베딩 예측
        # 실제 서비스에서는 사용자의 최근 시퀀스를 활용해야 함
        dummy_seq = torch.zeros((1, 50, self.model.embedding_dim), device=self.device)  # 임의의 시퀀스
        with torch.no_grad():
            predicted_embedding = self.model(dummy_seq)  # shape: (1, embedding_dim)
        
        # 예측 임베딩과 각 후보 임베딩 간의 유사도 계산
        predicted_vec = predicted_embedding.cpu().numpy()[0]
        scores = []
        for emb in candidate_embeddings:
            # 코사인 유사도 또는 다른 유사도 측정 사용
            similarity = np.dot(predicted_vec, emb) / (np.linalg.norm(predicted_vec) * np.linalg.norm(emb) + 1e-8)
            scores.append(similarity)
        return scores

    def save(self, path: str) -> None:
        torch.save(self.model.state_dict(), path)

    def load(self, path: str) -> None:
        self.model.load_state_dict(torch.load(path, map_location=self.device))
