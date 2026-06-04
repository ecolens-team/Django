"""
 BioCLIP-2 fine-tuning for Jordanian plant & insect species.

Approach:
  1. Load the pre-trained BioCLIP-2 model (open_clip).
  2. Initialise a linear classification head from the text encoder's
     embeddings of each class name (
  3. Attach LoRA adapters to the vision encoder and train only the
     adapters + head (parameter-efficient fine-tuning via PEFT).
  4. Handle class imbalance with weighted sampling + weighted loss.

Expects the dataset as ImageFolder-style directories, one folder per
species (named "Genus_species"), under PLANTS_DIR and INSECTS_DIR.
"""

import os
import time
import json
import torch
import open_clip
import torch.nn as nn
import numpy as np
from collections import defaultdict
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
from peft import get_peft_model, LoraConfig
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import precision_recall_fscore_support
from tqdm import tqdm

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Using device: {device}")

# 1. Paths and dataset linking
PLANTS_DIR = '/workspace/ecolens_data/_output_ (1)/ecolens_plants'
INSECTS_DIR = '/workspace/ecolens_data/_output_/ecolens_insects'
COMBINED_DIR = '/workspace/combined_data'
CHECKPOINT_DIR = '/workspace/ecolens_checkpoints'

os.makedirs(COMBINED_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# Species with too few images are dropped
MIN_IMAGES_REQUIRED = 10
included_species, excluded_species = 0, 0

# Symlink the plant and insect class folders into a single combined directory
# so a single ImageFolder can read them all.
print(f"[INFO] Linking datasets (filtering classes with < {MIN_IMAGES_REQUIRED} images)...")
for src_dir in [PLANTS_DIR, INSECTS_DIR]:
    if os.path.exists(src_dir):
        for class_name in os.listdir(src_dir):
            src_class_path = os.path.join(src_dir, class_name)
            if os.path.isdir(src_class_path):
                num_images = len([f for f in os.listdir(src_class_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                if num_images < MIN_IMAGES_REQUIRED:
                    excluded_species += 1
                    continue

                dst_class_path = os.path.join(COMBINED_DIR, class_name)
                if not os.path.exists(dst_class_path):
                    os.symlink(src_class_path, dst_class_path)
                    included_species += 1

print(f"--- Species included: {included_species} | excluded: {excluded_species} ---")


# 2. Image transforms
print("[INFO] Setting up transforms...")
_, _, base_val_transform = open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip-2')
clip_normalization = base_val_transform.transforms[-1]

# Augmentation
train_transform = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomRotation(degrees=15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    clip_normalization
])

full_train_dataset = datasets.ImageFolder(COMBINED_DIR, transform=train_transform)
full_val_dataset = datasets.ImageFolder(COMBINED_DIR, transform=base_val_transform)

class_names = full_train_dataset.classes
num_classes = len(class_names)

with open(os.path.join(CHECKPOINT_DIR, 'ecolens_classes.json'), 'w', encoding='utf-8') as f:
    json.dump(class_names, f, ensure_ascii=False, indent=4)


# Split per class so every species is represented in each split.
targets = [s[1] for s in full_train_dataset.samples]
class_indices = defaultdict(list)
for idx, target in enumerate(targets):
    class_indices[target].append(idx)

train_idx, val_idx, test_idx = [], [], []
np.random.seed(42)

for c, indices in class_indices.items():
    np.random.shuffle(indices)
    n = len(indices)
    if n < 3:
        train_idx.extend(indices)
    else:
        v_split, t_split = max(1, int(0.1 * n)), max(1, int(0.1 * n))
        val_idx.extend(indices[:v_split])
        test_idx.extend(indices[v_split:v_split + t_split])
        train_idx.extend(indices[v_split + t_split:])

train_dataset = Subset(full_train_dataset, train_idx)
val_dataset = Subset(full_val_dataset, val_idx)

# 4. Class balancing
print("[INFO] Calculating class weights for balancing...")
train_targets = [targets[i] for i in train_idx]
class_counts = np.bincount(train_targets, minlength=num_classes)
class_counts = np.maximum(class_counts, 1)

weights = 1.0 / class_counts
weights = weights / weights.sum() * len(weights)
class_weights_tensor = torch.FloatTensor(weights).to(device)
criterion = nn.CrossEntropyLoss(weight=class_weights_tensor, label_smoothing=0.1)

sample_weights = [1.0 / class_counts[t] for t in train_targets]
budget_samples = len(train_idx)

sampler = WeightedRandomSampler(
    weights=sample_weights,
    num_samples=budget_samples,
    replacement=True
)

train_loader = DataLoader(train_dataset, batch_size=32, sampler=sampler, num_workers=2, pin_memory=True)
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=2, pin_memory=True)

# 5. Zero-shot initialisation of the classification head
print("[INFO] Loading BioCLIP-2 for text embeddings...")
base_model, _, _ = open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip-2', device=device)
tokenizer = open_clip.get_tokenizer('hf-hub:imageomics/bioclip-2')

classification_head = nn.Linear(768, num_classes, bias=False).to(device)

print("[INFO] Generating head weights from the text encoder...")
with torch.no_grad():
    text_prompts = [f"a photo of {name.replace('_', ' ')}, a species from Jordan." for name in class_names]
    text_features = []

    batch_size = 100
    for i in range(0, len(text_prompts), batch_size):
        batch_tokens = tokenizer(text_prompts[i:i + batch_size]).to(device)
        batch_features = base_model.encode_text(batch_tokens)
        batch_features /= batch_features.norm(dim=-1, keepdim=True)
        text_features.append(batch_features)

    text_emb = torch.cat(text_features, dim=0)
    classification_head.weight.data = text_emb


# 6. LoRA on the vision encoder
print("[INFO] Attaching LoRA to the vision encoder...")
vision_model = base_model.visual
for param in vision_model.parameters():
    param.requires_grad = False

config = LoraConfig(
    r=16, lora_alpha=32, target_modules=["c_fc", "c_proj", "out_proj"], lora_dropout=0.1, bias="none"
)
lora_model = get_peft_model(vision_model, config)
lora_model.to(device)

# Lower LR for the adapters, higher LR for the freshly trained head.
optimizer = torch.optim.AdamW([
    {'params': lora_model.parameters(), 'lr': 5e-5},
    {'params': classification_head.parameters(), 'lr': 1e-3}
])
scheduler = CosineAnnealingLR(optimizer, T_max=5)


# 7. Training loop
NUM_EPOCHS = 5
best_val_f1 = 0.0

print("[INFO] Starting training...")

for epoch in range(NUM_EPOCHS):
    print(f"\n--- Epoch {epoch + 1}/{NUM_EPOCHS} ---")
    print(f"[INFO] Current head LR: {optimizer.param_groups[1]['lr']:.6f}")

    lora_model.train()
    classification_head.train()
    running_loss = 0.0

    total_batches = len(train_loader)
    ten_percent_step = max(1, total_batches // 10)

    for step, (images, labels) in enumerate(tqdm(train_loader, desc="Training")):
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        features = lora_model(images)
        outputs = classification_head(features)

        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item()

        if (step + 1) % ten_percent_step == 0 or (step + 1) == total_batches:
            current_loss = running_loss / (step + 1)
            percent_complete = int(((step + 1) / total_batches) * 100)
            current_time = time.strftime("%H:%M:%S")
            print(f"[{current_time}] Epoch {epoch + 1} progress: {percent_complete}% ({step + 1}/{total_batches}) | Loss: {current_loss:.4f}")

    avg_train_loss = running_loss / len(train_loader)
    scheduler.step()

    lora_model.eval()
    classification_head.eval()
    all_preds, all_labels = [], []
    top5_correct, total = 0, 0

    with torch.no_grad():
        for images, labels in tqdm(val_loader, desc="Validating"):
            images, labels = images.to(device), labels.to(device)

            features = lora_model(images)
            outputs = classification_head(features)

            _, predicted = torch.max(outputs.data, 1)
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

            _, top5_preds = outputs.topk(5, 1, True, True)
            for i in range(labels.size(0)):
                if labels[i] in top5_preds[i]:
                    top5_correct += 1
            total += labels.size(0)

    precision, recall, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro', zero_division=0)
    top1_acc = 100 * sum(p == l for p, l in zip(all_preds, all_labels)) / total
    top5_acc = 100 * top5_correct / total

    print(f"\nTraining loss: {avg_train_loss:.4f}")
    print(f"Val Top-1: {top1_acc:.2f}% | Val Top-5: {top5_acc:.2f}%")
    print(f"Val Macro F1: {f1:.4f} | Precision: {precision:.4f} | Recall: {recall:.4f}")

    epoch_dir = os.path.join(CHECKPOINT_DIR, f"epoch_{epoch + 1}")
    os.makedirs(epoch_dir, exist_ok=True)

    lora_model.save_pretrained(epoch_dir)
    torch.save(classification_head.state_dict(), os.path.join(epoch_dir, "head.pth"))

    training_state = {
        'epoch': epoch + 1,
        'best_val_f1': best_val_f1,
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict()
    }
    torch.save(training_state, os.path.join(epoch_dir, "training_state.pth"))
    print(f"[INFO] Checkpoint saved to {epoch_dir}")

print("\n[INFO] Training complete.")
