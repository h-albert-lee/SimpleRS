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
        self.max_seq_length = max_seq_length  # 최대 시퀀스 길이 저장
        self.model = TransformerEncoder(embedding_dim, num_heads, num_layers, max_seq_length).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()

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
                # 시퀀스를 텐서로 변환
                seq_tensor = torch.tensor(sequence, dtype=torch.float, device=self.device)  # shape: (T, embedding_dim)
                # 왼쪽 패딩 적용하여 고정 길이로 맞춤
                padded_seq = pad_sequence_left(seq_tensor, self.max_seq_length)  # shape: (max_seq_length, embedding_dim)
                # 배치 차원 추가: (1, max_seq_length, embedding_dim)
                padded_seq = padded_seq.unsqueeze(0)

                # 예측 목표: 시퀀스의 마지막 아이템(embedding)
                target = padded_seq[:, -1, :]  # shape: (1, embedding_dim)
                # 입력 시퀀스: 마지막 아이템을 제외한 시퀀스
                input_seq = padded_seq[:, :-1, :]  # shape: (1, max_seq_length-1, embedding_dim)
                
                self.optimizer.zero_grad()
                output = self.model(input_seq)  
                loss = self.criterion(output, target)
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
            print(f"Epoch {epoch+1}, Loss: {total_loss}")

    def predict(self, user_id: str, candidate_embeddings: List[np.ndarray]) -> List[float]:
        """
        주어진 user_id에 대해 후보 콘텐츠 임베딩들의 유사도를 예측하여 점수 리스트 반환.
        candidate_embeddings: 추천 후보 콘텐츠들의 임베딩 리스트
        """
        self.model.eval()
        
        # 1. 사용자 최근 시퀀스 가져오기 (프로덕션용으로 실제 구현 필요)
        # 이 부분은 실제 사용자 행동 데이터를 조회하는 로직으로 교체해야 합니다.
        user_sequence_embeddings = self.retrieve_user_sequence(user_id)
        
        # 2. 사용자 시퀀스를 텐서로 변환 및 왼쪽 패딩 적용
        if user_sequence_embeddings:
            seq_tensor = torch.tensor(user_sequence_embeddings, dtype=torch.float, device=self.device)
        else:
            # 사용자의 이력이 없으면, 임베딩 벡터를 0으로 채움
            seq_tensor = torch.zeros((1, self.model.embedding_dim), dtype=torch.float, device=self.device)
        
        padded_seq = pad_sequence_left(seq_tensor, self.max_seq_length)  # (max_seq_length, embedding_dim)
        padded_seq = padded_seq.unsqueeze(0)  # (1, max_seq_length, embedding_dim)
        
        # 3. 모델을 통한 다음 임베딩 예측
        with torch.no_grad():
            # 마지막 아이템 제외한 입력 시퀀스 준비
            input_seq = padded_seq[:, :-1, :]  # (1, max_seq_length-1, embedding_dim)
            predicted_embedding = self.model(input_seq)  # (1, embedding_dim)
        
        # 4. 예측 임베딩과 각 후보 임베딩 간의 유사도 계산 (코사인 유사도)
        predicted_vec = predicted_embedding.cpu().numpy()[0]
        scores = []
        for emb in candidate_embeddings:
            norm_pred = np.linalg.norm(predicted_vec) + 1e-8
            norm_emb = np.linalg.norm(emb) + 1e-8
            similarity = np.dot(predicted_vec, emb) / (norm_pred * norm_emb)
            scores.append(similarity)
        
        return scores

    def retrieve_user_sequence(self, user_id: str) -> List[List[float]]:
        """
        주어진 user_id에 대한 사용자 최근 행동 시퀀스를 임베딩 리스트 형태로 반환하는 함수.
        실제 프로덕션 환경에서는 데이터베이스나 로그 시스템에서 사용자 데이터를 조회하는 로직을 구현해야 함.
        현재는 더미 데이터를 반환.
        """
        # TODO: 실제 사용자 시퀀스 조회 및 임베딩 변환 로직 구현
        # 예시: return [embed_content(meta) for meta in get_user_history(user_id)]
        return []  # 더미로 빈 리스트 반환

    def save(self, path: str) -> None:
        torch.save(self.model.state_dict(), path)

    def load(self, path: str) -> None:
        self.model.load_state_dict(torch.load(path, map_location=self.device))

def pad_sequence_left(sequence: torch.Tensor, max_seq_length: int) -> torch.Tensor:
    """
    주어진 시퀀스(tensor)를 왼쪽에 패딩하여 max_seq_length 길이로 만듭니다.
    sequence: (seq_length, embedding_dim) 형태의 텐서
    반환: (max_seq_length, embedding_dim) 형태의 텐서
    """
    seq_length, embedding_dim = sequence.shape
    if seq_length >= max_seq_length:
        # 시퀀스가 이미 최대 길이 이상이면 마지막 max_seq_length 부분 사용
        return sequence[-max_seq_length:]
    else:
        padding_length = max_seq_length - seq_length
        padding = torch.zeros((padding_length, embedding_dim), dtype=sequence.dtype, device=sequence.device)
        padded_sequence = torch.cat((padding, sequence), dim=0)
        return padded_sequence
