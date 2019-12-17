import torch
import numpy as np
from dataset import PairedDataset, TestDataset
from torchvision import transforms
from utils.transforms import sobel_process, custom_greyscale_to_tensor
from torch.utils.data import DataLoader


def create_dataloaders(config):
    dset_A_name = config.dset_A_name
    dset_B_name = config.dset_B_name

    if dset_A_name == 'MNIST':
        dset_A_tf = transforms.Compose([
            transforms.RandomCrop(config.rand_crop_sz),
            transforms.Resize((config.input_sz, config.input_sz)),
            transforms.ToTensor(),
        ])
        dset_A_tf_test = transforms.Compose([
            transforms.Resize((config.input_sz, config.input_sz)),
            transforms.ToTensor(),
        ])
    elif dset_A_name == 'Fashion_MNIST':
        dset_A_tf = transforms.Compose([
            transforms.RandomCrop(config.rand_crop_sz),
            transforms.Resize((config.input_sz, config.input_sz)),
            transforms.ToTensor(),
        ])
        dset_A_tf_test = transforms.Compose([
            transforms.Resize((config.input_sz, config.input_sz)),
            transforms.ToTensor(),
        ])

    if dset_B_name == 'SVHN':
        dset_B_tf = transforms.Compose([
            transforms.CenterCrop(config.rand_crop_sz),
            transforms.Resize((config.input_sz, config.input_sz)),
            transforms.RandomApply(
                [transforms.RandomRotation(config.rot_val)], p=0.5),
            transforms.ColorJitter(brightness=0.4, contrast=0.4,
                                   saturation=0.4, hue=0.125),
            custom_greyscale_to_tensor(config.include_rgb),
        ])
        dset_B_tf_test = transforms.Compose([
            transforms.Resize((config.input_sz, config.input_sz)),
            custom_greyscale_to_tensor(config.include_rgb),
        ])
    elif dset_B_name == 'Fashion_WILD':
        dset_B_tf = transforms.Compose([
            transforms.RandomCrop(config.rand_crop_sz),
            transforms.Resize((config.input_sz, config.input_sz)),
            transforms.RandomApply(
                [transforms.RandomRotation(config.rot_val)], p=0.5),
            transforms.ColorJitter(brightness=0.4, contrast=0.4,
                                   saturation=0.4, hue=0.125),
            custom_greyscale_to_tensor(config.include_rgb),
        ])
        dset_B_tf_test = transforms.Compose([
            transforms.Resize((config.input_sz, config.input_sz)),
            custom_greyscale_to_tensor(config.include_rgb),
        ])

    train_dset = PairedDataset(config, dset_A_name, dset_B_name, dset_A_tf, dset_B_tf)

    dataloaders_head_A = []
    dataloader_head_B = []
    for i in range(config.num_dataloaders):
        loader_A = DataLoader(train_dset, batch_size=config.batch_sz, shuffle=True)
        loader_B = DataLoader(train_dset, batch_size=config.batch_sz, shuffle=True)
        dataloaders_head_A.append(loader_A)
        dataloader_head_B.append(loader_B)

    src_test_dset = TestDataset(config, dset_A_name, dset_A_tf_test)
    dest_test_dset = TestDataset(config, dset_B_name, dset_B_tf_test)

    src_test_loader = DataLoader(src_test_dset, batch_size=config.batch_sz, shuffle=True)
    dest_test_loader = DataLoader(dest_test_dset, batch_size=config.batch_sz, shuffle=True)

    return dataloaders_head_A, dataloader_head_B, src_test_loader, dest_test_loader


def get_preds_and_targets(config, net_model, dataloader):
    dataset_size = len(dataloader.dataset)
    preds = torch.zeros(config.num_sub_heads, dataset_size)
    targets = torch.zeros(dataset_size)
    batch_sz = config.batch_sz

    for b_i, batch in enumerate(dataloader):
        src_x, label = batch
        src_x = src_x.cuda()

        src_x = sobel_process(src_x, config.include_rgb)

        with torch.no_grad():
            src_y = net_model(src_x)  # (batch_size, num_classes)

        start_i = b_i * batch_sz
        end_i = start_i + label.size(0)
        for i in range(config.num_sub_heads):
            preds[i][start_i:end_i] = torch.argmax(src_y[i], dim=1)

        targets[start_i:end_i] = label

    return preds, targets


def get_latent_and_targets(config, net_model, val_loader, dataset):
    dataset_size = len(dataset)
    latents = torch.zeros(config.num_sub_heads, dataset_size, 10)
    targets = torch.zeros(dataset_size)
    batch_sz = config.batch_sz

    for b_i, batch in enumerate(val_loader):
        src_x, label = batch
        src_x = src_x.cuda()

        src_x = sobel_process(src_x, config.include_rgb)

        with torch.no_grad():
            src_y = net_model(src_x)  # (batch_size, num_classes)

        start_i = b_i * batch_sz
        end_i = start_i + label.size(0)
        for i in range(config.num_sub_heads):
            latents[i][start_i:end_i] = src_y[i]

        targets[start_i:end_i] = label

    return latents, targets


def get_preds_actual_class(preds, matches, config):
    num_samples = preds.size(0)
    new_preds = torch.zeros(num_samples, dtype=preds.dtype)
    found = torch.zeros(config.num_classes)

    if torch.cuda.is_available():
        new_preds = new_preds.cuda()

    for pred_i, target_i in matches:
        new_preds[torch.eq(preds, int(pred_i))] = torch.from_numpy(np.array(target_i)).cuda().int().item()
        found[pred_i] = 1

    assert (found.sum() == config.num_classes)  # each output_k must get mapped

    return new_preds
