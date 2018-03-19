# detection algorithm validation pipeline
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pickle
import cv2
import glob
from lesson_functions import *
from scipy.ndimage.measurements import label

# Define a single function that can extract features using hog sub-sampling and make predictions
def find_cars(img, svc, X_scaler, orient, pix_per_cell, cell_per_block, spatial_size, hist_bins):
    
    draw_img = np.copy(img)
    box_list = []
    # convert uint8 image to float32 (jpg image)
    if img.dtype == "uint8":
        img = img.astype(np.float32)/255
    

    # assign different scale for different ranges
    # [ystart, ystop, scale, cells_per_step]
    scaletable = [[400, 500, 1.0, 1],
                  [400, 600, 2.0, 1], 
                  [500, 656, 2.0, 2]]
    
    for param in scaletable:
        ystart = param[0]
        ystop = param[1]
        scale = param[2]
        cells_per_step = param[3]
        img_tosearch = img[ystart:ystop,:,:]
        # change color space, NOTE: need to change in training script as well
        ctrans_tosearch = convert_color(img_tosearch, conv='RGB2YCrCb')
        if scale != 1:
            imshape = ctrans_tosearch.shape
            ctrans_tosearch = cv2.resize(ctrans_tosearch, (np.int(imshape[1]/scale), np.int(imshape[0]/scale)))
            
        ch1 = ctrans_tosearch[:,:,0]
        ch2 = ctrans_tosearch[:,:,1]
        ch3 = ctrans_tosearch[:,:,2]

        # Define blocks and steps as above
        nxblocks = (ch1.shape[1] // pix_per_cell) - cell_per_block + 1
        nyblocks = (ch1.shape[0] // pix_per_cell) - cell_per_block + 1 
        nfeat_per_block = orient*cell_per_block**2
        
        # 64 was the orginal sampling rate, with 8 cells and 8 pix per cell
        window = 64
        nblocks_per_window = (window // pix_per_cell) - cell_per_block + 1
        #cells_per_step = 1  # Instead of overlap, define how many cells to step
        nxsteps = (nxblocks - nblocks_per_window) // cells_per_step + 1
        nysteps = (nyblocks - nblocks_per_window) // cells_per_step + 1
        
        # TODO: how to make sure hog feature is from (64,64) image?
        # Compute individual channel HOG features for the entire image
        hog1 = get_hog_features(ch1, orient, pix_per_cell, cell_per_block, feature_vec=False)
        hog2 = get_hog_features(ch2, orient, pix_per_cell, cell_per_block, feature_vec=False)
        hog3 = get_hog_features(ch3, orient, pix_per_cell, cell_per_block, feature_vec=False)
        
        for xb in range(nxsteps):
            for yb in range(nysteps):
                ypos = yb*cells_per_step
                xpos = xb*cells_per_step
                # Extract HOG for this patch

                hog_feat1 = hog1[ypos:ypos+nblocks_per_window, xpos:xpos+nblocks_per_window].ravel() 
                hog_feat2 = hog2[ypos:ypos+nblocks_per_window, xpos:xpos+nblocks_per_window].ravel() 
                hog_feat3 = hog3[ypos:ypos+nblocks_per_window, xpos:xpos+nblocks_per_window].ravel() 
                # hog channel change to all
                hog_features = np.hstack((hog_feat1, hog_feat2, hog_feat3))

                xleft = xpos*pix_per_cell
                ytop = ypos*pix_per_cell

                # Extract the image patch
                subimg = cv2.resize(ctrans_tosearch[ytop:ytop+window, xleft:xleft+window], (64,64))
              
                # Get color features
                spatial_features = bin_spatial(subimg, size=spatial_size)
                hist_features = color_hist(subimg, nbins=hist_bins)

                # Scale features and make a prediction
                test_features = X_scaler.transform(np.hstack((spatial_features, hist_features, hog_features)).reshape(1, -1))    
                #test_features = X_scaler.transform(np.hstack((shape_feat, hist_feat)).reshape(1, -1))    
                test_prediction = svc.predict(test_features)
                
                if test_prediction == 1:
                    xbox_left = np.int(xleft*scale)
                    ytop_draw = np.int(ytop*scale)
                    win_draw = np.int(window*scale)
                    drawbox = ((xbox_left, ytop_draw+ystart), (xbox_left+win_draw,ytop_draw+win_draw+ystart))
                    # filter false detections (100,700) (600, 400)
                    # (1280 482), (1000, 450) 
                    if (drawbox[0][0] >= 100+(700-drawbox[0][1])*500./300) and (drawbox[1][0] <= 1000+(drawbox[1][1]-450)*280./35):
                        # store a box list to generate heat map
                        box_list.append(drawbox)
                
    # draw all boxes on top
    for i in range(len(box_list)):
        cv2.rectangle(draw_img,box_list[i][0],box_list[i][1],(0,0,255),6)

    return draw_img, box_list


def add_heat(heatmap, bbox_list):
    # Iterate through list of bboxes
    for box in bbox_list:
        # Add += 1 for all pixels inside each bbox
        # Assuming each "box" takes the form ((x1, y1), (x2, y2))
        heatmap[box[0][1]:box[1][1], box[0][0]:box[1][0]] += 1

    # Return updated heatmap
    return heatmap# Iterate through list of bboxes
    
def apply_threshold(heatmap, threshold):
    # Zero out pixels below the threshold
    heatmap[heatmap <= threshold] = 0
    # Return thresholded map
    return heatmap

def draw_labeled_bboxes(img, labels):
    # Iterate through all detected cars
    for car_number in range(1, labels[1]+1):
        # Find pixels with each car_number label value
        nonzero = (labels[0] == car_number).nonzero()
        # Identify x and y values of those pixels
        nonzeroy = np.array(nonzero[0])
        nonzerox = np.array(nonzero[1])
        # Define a bounding box based on min/max x and y
        bbox = ((np.min(nonzerox), np.min(nonzeroy)), (np.max(nonzerox), np.max(nonzeroy)))
        bwidth = bbox[1][0] - bbox[0][0]
        bheight = bbox[1][1] - bbox[0][1]
        if (bwidth>=16) and (bheight>16):
            # Draw the box on the image
            cv2.rectangle(img, bbox[0], bbox[1], (0,0,255), 6)
    # Return the image
    return img

def getHeatmap(img, box_list):
    # generate raw heat map
    heat = np.zeros_like(img[:,:,0]).astype(np.float)

    # Add heat to each box in box list
    heat = add_heat(heat,box_list)
    return heat

def filterBox(img, heat):
    # filter car positions and output new heat map 
    # Apply threshold to help remove false positives
    heat = apply_threshold(heat,3)

    # Visualize the heatmap when displaying    
    heatmap = np.clip(heat, 0, 255)

    # Find final boxes from heatmap using label function
    labels = label(heatmap)

    draw_img = draw_labeled_bboxes(np.copy(img), labels)

    # overlay heatmp on the original image
    # x 840:1080, y 0 to 240
    heatmap_visual = heatmap*255./max(heatmap.max(),1)
    colorheat = cv2.applyColorMap(heatmap_visual.astype('uint8'), cv2.COLORMAP_HOT)
    #colorheat =  cv2.cvtColor(heatmap, cv2.COLORMAP_HOT)    
    resized_heat = cv2.resize(colorheat, (420, 240)) 
    for c in range(0, 3):
        # overlay detection video with 0.5 transparentcy
        draw_img[0:240, 840:1260, c] = (0.0*draw_img[0:240, 840:1260, c] + 1.0*resized_heat[:, :, c])
    return draw_img, heatmap


if __name__ == "__main__":
    # load a pe-trained svc model from a serialized (pickle) file
    modelname = "Trained_model/2018-03-19-trained_SVM.p"
    dist_pickle = pickle.load( open(modelname, "rb" ) )

    # get attributes of our svc object
    svc = dist_pickle["svc"]
    X_scaler = dist_pickle["scaler"]
    orient = dist_pickle["orient"]
    pix_per_cell = dist_pickle["pix_per_cell"]
    cell_per_block = dist_pickle["cell_per_block"]
    spatial_size = dist_pickle["spatial_size"]
    hist_bins = dist_pickle["hist_bins"]

    # read in all test images
    testimgs = glob.glob('test_images/video*')
    for imgf in testimgs:
        img = mpimg.imread(imgf)
        #img = mpimg.imread('test_images/test5.jpg')
        #img = mpimg.imread('test_images/video3.png')
        # convert uint8 image to float32 (jpg image)
        if img.dtype == "uint8":
            img = img.astype(np.float32)/255    

        # find cars with sliding window    
        out_img, box_list = find_cars(img, svc, X_scaler, orient, pix_per_cell, cell_per_block, spatial_size, hist_bins)

        # get raw heatmap
        heatmap_raw = getHeatmap(img, box_list)

        # filter car positions and output heat map    
        draw_img, heatmap = filterBox(img, heatmap_raw)


        fig = plt.figure()
        plt.subplot(131)
        plt.imshow(out_img)
        plt.title('Car Positions')
        plt.subplot(132)
        plt.imshow(draw_img)
        plt.title('Filtered Detection')
        plt.subplot(133)
        plt.imshow(heatmap, cmap='hot')
        plt.title('Heat Map')
        fig.tight_layout()



    plt.show()
        
