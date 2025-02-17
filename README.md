# CubMeta
The PyTorch implementation of the paper "Curriculum-Based Meta-learning". In this paper, we present a Curriculum-Based Meta-learning (CubMeta) method to train the meta-learner using tasks from easy to hard. Specifically, the framework of CubMeta is in a progressive way, and in each step, we design a module named BrotherNet to establish harder tasks and an effective learning scheme for obtaining an ensemble of stronger meta-learners. In this way, the meta-learner’s generalization ability can be progressively improved, and better
performance can be obtained even with fewer training tasks. 
![avatar](https://github.com/nobody-777/CubMeta/blob/master/framework.png)

## Prerequisites
- Python 3.5
- PyTorch >= 1.2
- TorchVision >= 0.2
- tqdm

## Dataset Preparation
### mini-ImageNet
- Training set: 64 classes (600 images per class)
- Val set: 16 classes
- Test set: 20 classes

### tiered-ImageNet
- Training set: 351 classes (600 images per class)
- Val set: 97 classes
- Test set: 160 classes

After downloading the dataset, please create a new folder named "images" under the folder "miniimagenet" or "tieredimagenet", and put all images in this folder. The provided data loader will read images from the "images" folder by default. Of course, it is also OK to change the read path. For example, for the miniimagenet dataset, please change the line 10 of "./dataloader/mini_imagenet.py" as the path of the downloaded images.

## Meta-training
### Meta-training using the single model
To train the single meta-leaner using tasks sampled from all base classes, you should use codes from the package trainer_single. For example, you can use the following script to train the ProtoNet with the pre-trained ResNet-12 backnone on the base classes of mini-ImageNet.
> python train_fsl.py  --max_epoch 50 --model_class ProtoNet  --backbone_class Res12 --dataset MiniImageNet --way 5 --query 15 --eval_query 15 --temperature 20 --step_size 10   --use_euclidean --model_name Stag1  --gpu 7 --lr 0.00001 --init_weights ./saves/initialization/miniimagenet/Res12-pre.pth
### Meta-training using our Curriculum-Based Meta-learning method
Since our method is a two-layer recursive version of the designed BrotherNet module, we give the implementation of the BrotherNet in trainer_ensemble package. 
For example, you can dirrectly perform the Demo.sh  in the package to train and test a specific meta-learner. 
> Demo.sh

## Meta-test
You can using the following script to test your trained model using tasks sampled from test set.
> python trainer_ensemble/test_fsl.py   --shot 5 --eval_shot 5 --num_test_episodes 3000   --test_model .your_trained_model_path --gpu 5

## Acknowledgement
Our implementations use the source code from the following repositories and users:
- [Few-Shot Learning via Embedding Adaptation with Set-to-Set Functions](https://github.com/Sha-Lab/FEAT), CVPR2020
- [Diversity with Cooperation: Ensemble Methods for Few-Shot Classification](https://github.com/dvornikita/fewshot_ensemble), ICCV2019

Thanks for their valuable work.

## Contact
If you have any questions about this implementation, please do not hesitate to contact with me. 

## Bibtex
> @inproceedings{cubmeta,  
>   author    = {Ji Zhang,  
>               Jingkuan Song,  
>               Yazhou Yao, and  
>               Lianli Gao},  
>   title     = {Curriculum-Based Meta-learning},  
>   booktitle = {ACM Multimedia},  
>   year      = {2021}  
>}


