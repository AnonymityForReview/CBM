import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from dataloader.samplers import CategoriesSampler
from models.protonet import ProtoNet
from models.matchnet import MatchNet
from models.feat import FEAT
from models.bilstm import BILSTM

class MultiGPUDataloader:
    def __init__(self, dataloader, num_device):
        self.dataloader = dataloader
        self.num_device = num_device

    def __len__(self):
        return len(self.dataloader) // self.num_device

    def __iter__(self):
        data_iter = iter(self.dataloader)
        done = False

        while not done:
            try:
                output_batch = ([], [])
                for _ in range(self.num_device):
                    batch = next(data_iter)
                    for i, v in enumerate(batch):
                        output_batch[i].append(v[None])
                
                yield ( torch.cat(_, dim=0) for _ in output_batch )
            except StopIteration:
                done = True
        return

def get_dataloader(args):
    if args.dataset == 'MiniImageNet':
        # Handle MiniImageNet
        from dataloader.mini_imagenet import MiniImageNet as Dataset
    elif args.dataset == 'CUB':
        from dataloader.cub import CUB as Dataset
    elif args.dataset == 'TieredImageNet':
        from dataloader.tiered_imagenet import tieredImageNet as Dataset
    else:
        raise ValueError('Non-supported Dataset.')

    num_device = torch.cuda.device_count()
    num_episodes = args.episodes_per_epoch*num_device if args.multi_gpu else args.episodes_per_epoch
    num_workers = args.num_workers*num_device if args.multi_gpu else args.num_workers
    # trainset = Dataset('train', args, augment=args.augment)
    t_subset_a = Dataset(args.subset_A, args, augment=args.augment)
    args.num_class_a = t_subset_a.num_class
    train_sampler_a = CategoriesSampler(t_subset_a.label, num_episodes, max(args.way, args.num_classes), args.shot + args.query)
    train_loader_a = DataLoader(dataset=t_subset_a, num_workers=num_workers, batch_sampler=train_sampler_a, pin_memory=True)

    t_subset_b = Dataset(args.subset_B, args, augment=args.augment)
    args.num_class_b = t_subset_b.num_class
    train_sampler_b = CategoriesSampler(t_subset_b.label, num_episodes, max(args.way, args.num_classes), args.shot + args.query)
    train_loader_b = DataLoader(dataset=t_subset_b, num_workers=num_workers, batch_sampler=train_sampler_b, pin_memory=True)

    valset = Dataset('val', args)
    val_sampler = CategoriesSampler(valset.label,
                            args.num_eval_episodes,
                            args.eval_way, args.eval_shot + args.eval_query)
    val_loader = DataLoader(dataset=valset,
                            batch_sampler=val_sampler,
                            num_workers=args.num_workers,
                            pin_memory=True)

    testset = Dataset('test', args)
    test_sampler = CategoriesSampler(testset.label,
                            args.num_test_episodes, # args.num_eval_episodes,
                            args.eval_way, args.eval_shot + args.eval_query)
    test_loader = DataLoader(dataset=testset,
                            batch_sampler=test_sampler,
                            num_workers=args.num_workers,
                            pin_memory=True,
                            )

    return train_loader_a, train_loader_b, val_loader, test_loader

def prepare_models(args):
    para_models = []
    # load_state_dict(torch.load(args.trained_models)['params_a'])
    if args.distill:
        for i in ['params_a', 'params_b']:
            model_fn = eval(args.model_class)(args)
            if args.trained_models is not None:
                model_dict = model_fn.state_dict()
                pretrained_dict = torch.load(args.trained_models)[i]
                if args.backbone_class == 'ConvNet':
                    pretrained_dict = {'encoder.' + k: v for k, v in pretrained_dict.items()}
                pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict}
                # print(pretrained_dict.keys())
                model_dict.update(pretrained_dict)
                model_fn.load_state_dict(model_dict)

            if torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True

            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            model = model_fn.to(device)
            if args.multi_gpu:
                model.encoder = nn.DataParallel(model.encoder, dim=0)
                para_model = model.to(device)
            else:
                para_model = model.to(device)
            para_models.append(para_model)

        # print("\n!!!!!! Knowledge distillation for each model using the rest (one) subset !!!!!! \n")

    else:
        for i in range(2):
            model_fn = eval(args.model_class)(args)
            # load pre-trained model (no FC weights)
            if args.init_weights is not None:
                model_dict = model_fn.state_dict()
                pretrained_dict = torch.load(args.init_weights)['params']
                # if args.backbone_class == 'ConvNet':
                #     pretrained_dict = {'encoder.' + k: v for k, v in pretrained_dict.items()}
                pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict}
                # print(pretrained_dict.keys())
                model_dict.update(pretrained_dict)
                model_fn.load_state_dict(model_dict)

            if torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True

            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            model = model_fn.to(device)
            if args.multi_gpu:
                model.encoder = nn.DataParallel(model.encoder, dim=0)
                para_model = model.to(device)
            else:
                para_model = model.to(device)
            para_models.append(para_model)

        # print("\nPre-trained backbones are loaded!")

    return para_models


def prepare_optimizer(models, args):
    top_para = [[v for k,v in x.named_parameters() if 'encoder' not in k] for x in models]
    # as in the literature, we use ADAM for ConvNet and SGD for other backbones

    if args.backbone_class == 'ConvNet':
        optimizer = optim.Adam(
            [{'params': models[0].encoder.parameters()},
             {'params': models[1].encoder.parameters()},
             {'params': top_para[0], 'lr': args.lr * args.lr_mul},
             {'params': top_para[1], 'lr': args.lr * args.lr_mul}],
            lr=args.lr,
            # weight_decay=args.weight_decay, do not use weight_decay here
        )
    else:
        optimizer = optim.SGD(
            [{'params': models[0].encoder.parameters()},
             {'params': models[1].encoder.parameters()},
             {'params': top_para[0], 'lr': args.lr * args.lr_mul},
             {'params': top_para[1], 'lr': args.lr * args.lr_mul}],
            lr=args.lr,
            momentum=args.mom,
            nesterov=True,
            weight_decay=args.weight_decay
        )

    if args.lr_scheduler == 'step':
        lr_scheduler = optim.lr_scheduler.StepLR(
                            optimizer,
                            step_size=int(args.step_size),
                            gamma=args.gamma
                        )
    elif args.lr_scheduler == 'multistep':
        lr_scheduler = optim.lr_scheduler.MultiStepLR(
                            optimizer,
                            milestones=[int(_) for _ in args.step_size.split(',')],
                            gamma=args.gamma,
                        )
    elif args.lr_scheduler == 'cosine':
        lr_scheduler = optim.lr_scheduler.CosineAnnealingLR(
                            optimizer,
                            args.max_epoch,
                            eta_min=0   # a tuning parameter
                        )
    else:
        raise ValueError('No Such Scheduler')

    return optimizer, lr_scheduler
