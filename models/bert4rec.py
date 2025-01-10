import torch
import torch.nn as nn
from typing import Any, List
from models.base_model import BaseModel

class TransformerEncoder(nn.Module):
    def __init__(self, num_items: int, embedding_dim: int = 64, num_heads: int = 4, num_layers: int = 2, max_seq_length: int = 50):
        super(TransformerEncoder, self).__init__()
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        self.position_embedding = nn.Embedding(max_seq_length, embedding_dim)
        encoder_layer = nn.TransformerEncoderLayer(d_model=embedding_dim, nhead=num_heads)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output_layer = nn.Linear(embedding_dim, num_items)

    def forward(self, input_seq):
        # input_seq: (batch_size, seq_length)
        seq_length = input_seq.size(1)
        positions = torch.arange(seq_length, device=input_seq.device).unsqueeze(0).expand_as(input_seq)
        embeddings = self.item_embedding(input_seq) + self.position_embedding(positions)
        embeddings = embeddings.permute(1, 0, 2)  # Transformer expects (seq_length, batch_size, embedding_dim)
        transformer_out = self.transformer_encoder(embeddings)
        transformer_out = transformer_out.permute(1, 0, 2)  # (batch_size, seq_length, embedding_dim)
        # 마지막 타임스텝 출력으로 다음 아이템 예측
        logits = self.output_layer(transformer_out[:, -1, :])
        return logits

class BERT4RecModel(BaseModel):
    def __init__(self, num_items: int = 1000, embedding_dim: int = 64, **kwargs):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = TransformerEncoder(num_items, embedding_dim, **kwargs).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.CrossEntropyLoss()

    def train(self, data: Any) -> None:
        """
        data는 (input_seq, target_item) 형태의 튜플 리스트라고 가정
        """
        self.model.train()
        epochs = 5
        for epoch in range(epochs):
            total_loss = 0.0
            for input_seq, target_item in data:
                input_tensor = torch.tensor(input_seq, dtype=torch.long, device=self.device).unsqueeze(0)  # 배치 사이즈=1
                target_tensor = torch.tensor([target_item], dtype=torch.long, device=self.device)

                self.optimizer.zero_grad()
                logits = self.model(input_tensor)
                loss = self.criterion(logits, target_tensor)
                loss.backward()
                self.optimizer.step()

                total_loss += loss.item()
            print(f"Epoch {epoch+1}, Loss: {total_loss}")

    def predict(self, user_id: str, candidates: List[Any]) -> List[Any]:
        """
        주어진 사용자에 대해 시퀀스 기반 추천 점수 계산.
        단순화를 위해 user_id는 사용하지 않으며, 최신 시퀀스를 사용한다고 가정.
        """
        self.model.eval()
        # 실제 구현 시 사용자별 최근 시퀀스 필요
        # 여기서는 dummy 시퀀스를 사용
        dummy_seq = [0] * 50  # 길이 50의 더미 시퀀스
        input_tensor = torch.tensor(dummy_seq, dtype=torch.long, device=self.device).unsqueeze(0)
        with torch.no_grad():
            logits = self.model(input_tensor)
        scores = logits.cpu().tolist()[0]
        # 후보 리스트와 점수를 매핑하여 반환
        return list(zip(candidates, scores[:len(candidates)]))

    def save(self, path: str) -> None:
        torch.save(self.model.state_dict(), path)

    def load(self, path: str) -> None:
        self.model.load_state_dict(torch.load(path, map_location=self.device))
