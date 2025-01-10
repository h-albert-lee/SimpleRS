import torch
import torch.nn as nn
import torch.optim as optim
from typing import Any, List
from models.base_model import BaseModel

class MatrixFactorization(nn.Module):
    def __init__(self, num_users: int, num_items: int, embedding_dim: int = 50):
        super(MatrixFactorization, self).__init__()
        self.user_embeddings = nn.Embedding(num_users, embedding_dim)
        self.item_embeddings = nn.Embedding(num_items, embedding_dim)

    def forward(self, user_indices, item_indices):
        user_embeds = self.user_embeddings(user_indices)
        item_embeds = self.item_embeddings(item_indices)
        # 내적(dot product)으로 예측 점수 계산
        return (user_embeds * item_embeds).sum(1)

class CollaborativeFilteringModel(BaseModel):
    def __init__(self, num_users: int = 1000, num_items: int = 1000, embedding_dim: int = 50, lr: float = 0.001):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = MatrixFactorization(num_users, num_items, embedding_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.criterion = nn.MSELoss()

    def train(self, data: Any) -> None:
        """
        data는 (user_id, item_id, rating) 형태의 튜플 리스트라고 가정
        """
        self.model.train()
        epochs = 5  # 간단한 예제로 몇 epoch만
        for epoch in range(epochs):
            total_loss = 0.0
            for user_id, item_id, rating in data:
                user = torch.tensor([user_id], device=self.device)
                item = torch.tensor([item_id], device=self.device)
                target = torch.tensor([rating], dtype=torch.float, device=self.device)

                self.optimizer.zero_grad()
                prediction = self.model(user, item)
                loss = self.criterion(prediction, target)
                loss.backward()
                self.optimizer.step()

                total_loss += loss.item()
            print(f"Epoch {epoch+1}, Loss: {total_loss}")

    def predict(self, user_id: str, candidates: List[Any]) -> List[Any]:
        """
        간단히 user_id에 해당하는 사용자의 item에 대한 예측 점수를 반환
        candidates는 item_id 리스트라고 가정
        """
        self.model.eval()
        user_idx = torch.tensor([int(user_id)] * len(candidates), device=self.device)
        item_indices = torch.tensor(candidates, device=self.device)
        with torch.no_grad():
            scores = self.model(user_idx, item_indices)
        # 후보와 점수를 튜플로 묶어 반환
        return list(zip(candidates, scores.cpu().tolist()))

    def save(self, path: str) -> None:
        torch.save(self.model.state_dict(), path)

    def load(self, path: str) -> None:
        self.model.load_state_dict(torch.load(path, map_location=self.device))
