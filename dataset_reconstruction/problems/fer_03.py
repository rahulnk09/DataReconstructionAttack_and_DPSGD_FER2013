import torch
from torch.utils.data import Dataset, DataLoader, Subset
import pandas as pd
import numpy as np
import torchvision.transforms as transforms

# Custom Dataset for loading data from CSV files
class FER2013CSV(Dataset):
    def __init__(self, csv_file, transform=None):
        self.data = pd.read_csv(csv_file)
        self.transform = transform if transform is not None else transforms.ToTensor()

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        label = int(self.data.iloc[idx]['emotion'])
        pixels = np.array(self.data.iloc[idx]['pixels'].split(), dtype=np.uint8).reshape(48, 48)

        if self.transform:
            pixels = self.transform(pixels)

        return pixels, label

# Helper function to load subset of the dataset
def load_bound_dataset(dataset, batch_size, shuffle=False, start=None, end=None, **kwargs):
    def _bound_dataset(dataset, start, end):
        if start is None:
            start = 0
        if end is None:
            end = len(dataset)
        return Subset(dataset, range(start, end))

    dataset = _bound_dataset(dataset, start, end)
    return DataLoader(dataset, batch_size, shuffle=shuffle, **kwargs)

# Load FER2013 data from CSV
def load_fer2013_from_csv(csv_file, batch_size, start=None, end=None, shuffle=False, transform=None, **kwargs):
    dataset = FER2013CSV(csv_file, transform=transform)
    return load_bound_dataset(dataset, batch_size, shuffle=shuffle, start=start, end=end, **kwargs)

# Convert labels for binary classification
def create_labels(y0):
    labels_dict = {0: -1, 1: -1, 2: -1, 3: 1, 4: 0, 5: -1, 6: -1, 7: -1, 8: -1, 9: -1}
    y0 = torch.stack([torch.tensor(labels_dict[int(cur_y)]) for cur_y in y0])
    return y0

# Balance data for binary classification
def get_balanced_data(args, data_loader, data_amount):
    print('BALANCING DATASET...')
    data_amount_per_class = data_amount // 2

    labels_counter = {1: 0, 0: 0}
    x0, y0 = [], []
    got_enough = False
    for bx, by in data_loader:
        by = create_labels(by)
        for i in range(len(bx)):
            if int(by[i]) == -1:
                continue
            elif labels_counter[int(by[i])] < data_amount_per_class:
                labels_counter[int(by[i])] += 1
                x0.append(bx[i])
                y0.append(by[i])
            if (labels_counter[0] >= data_amount_per_class) and (labels_counter[1] >= data_amount_per_class):
                got_enough = True
                break
        if got_enough:
            break
    x0, y0 = torch.stack(x0), torch.stack(y0)
    return x0, y0

# Main data loading function for FER2013
def load_fer2013_data(args):
    print('TRAINSET BALANCED')
    train_loader = load_fer2013_from_csv(
        csv_file=f"{args.datasets_dir}/fer2013/train.csv",
        batch_size=100,
        start=0,
        end=50000,
        shuffle=False
    )
    x0, y0 = get_balanced_data(args, train_loader, args.data_amount)

    print('LOADING TESTSET')
    assert not args.data_use_test or (args.data_use_test and args.data_test_amount >= 2), \
        f"args.data_use_test={args.data_use_test} but args.data_test_amount={args.data_test_amount}"
    test_loader = load_fer2013_from_csv(
        csv_file=f"{args.datasets_dir}/fer2013/test.csv",
        batch_size=100,
        start=0,
        end=10000,
        shuffle=False
    )
    x0_test, y0_test = get_balanced_data(args, test_loader, args.data_test_amount)

    # Move to specified device and type
    x0, y0 = move_to_type_device(x0, y0, args.device)
    x0_test, y0_test = move_to_type_device(x0_test, y0_test, args.device)

    print(f'BALANCE: 0: {y0[y0 == 0].shape[0]}, 1: {y0[y0 == 1].shape[0]}')
    return [(x0, y0)], [(x0_test, y0_test)], None

# Move data to specified device and dtype
def move_to_type_device(x, y, device):
    print('X:', x.shape)
    print('y:', y.shape)
    x = x.to(torch.get_default_dtype())
    y = y.to(torch.get_default_dtype())
    x, y = x.to(device), y.to(device)
    return x, y

# Initialize data loader with specified arguments
def get_dataloader(args):
    args.input_dim = 48 * 48 * 1
    args.num_classes = 2
    args.output_dim = 1
    args.dataset = 'fer2013'

    if args.run_mode == 'reconstruct':
        args.extraction_data_amount = args.extraction_data_amount_per_class * args.num_classes

    args.data_amount = args.data_per_class_train * args.num_classes
    args.data_use_test = True
    args.data_test_amount = 1000

    data_loader = load_fer2013_data(args)
    return data_loader
