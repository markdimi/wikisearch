# -*- coding: utf-8 -*-
""" Provides methods for applying clustering on a text document collection.
"""
import re
import time
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.externals import joblib
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import Normalizer
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.stem.snowball import SnowballStemmer

def tokenize(text):
    """ Takes a String as input and returns a list of its tokens.

        Args:
            text (str): A string object.

        Returns:
            filtered_tokens: A list of the tokens in the string after removing
                duplicates and tokens that contain only numbers.

    """
    filtered_tokens = []
    tokens = [word.lower() for sent in nltk.sent_tokenize(text) for word in
              nltk.word_tokenize(sent)]
    # Remove tokens that do not contain letters.
    for token in tokens:
        if re.search('[a-zA-Z]', token):
            filtered_tokens.append(token)
    return filtered_tokens

def stem(tokens):
    """ Takes a list of tokens as input and stems each entry.

        NLTK's SnowballStemmer is used for the stemming.

        Args:
            tokens (:list:'str'): A list of tokens.
        Returns:
            stems (:list:'str'): The list containing the stems of the tokens
            given as input.

    """
    stemmer = SnowballStemmer('english')
    stems = [stemmer.stem(token) for token in tokens]

    return stems

def tokenizer(text):
    """ Tokenizes and then stems a given text.

    Simply combines the tokenize() and stem() methods. This method is used
    by by the TfidfVectorizer for the calculation of the Tf/Idf matrix.

    Args:
        text (str): A string object.

    Returns:
        stems (:list:'str'): A list containing the stems of the input string.
    """
    stems = stem(tokenize(text))
    return stems


class ClusterMaker(object):
    """ Wrapper for quickly applying some clustering algorithms.

    Applies clustering using the kmeans or hac algorithm.

    Args:
        n_clusters (int): The number of clusters to be created.
        n_dimensions (int): When given a value, specifies the number of dimensions
            of the vector space after applying Latent Semantic Analysis. Defaults
            to None.

    Attributes:
        n_clusters (int): The number of clusters to be created.
        n_dimensions (int): When given a value, specifies the number of dimensions
            of the vector space after applying Latent Semantic Analysis. Defaults
            to None.
    """
    def __init__(self, n_clusters, n_dimensions=None):
        self.n_clusters = n_clusters
        self.n_dimensions = n_dimensions

    @staticmethod
    def extract_tfidf(corpus):
        """ Calculates the Tf/Idf matrix of the document collection.

        The Tf/Idf matrix is in sparse matrix format. After calculation,
        the matrix and the features of the collection are saved in files.

        Args:
            corpus (:obj:'Corpus'): The Corpus object of the document collection.

        Returns:
           tfidf_matrix (sparse matrix): The Tf/idf matrix of the document collection.

        """
        # Initialize the vectorizer.
        vectorizer = TfidfVectorizer(max_df=0.5, min_df=2, max_features=10000,
                                     use_idf=True, stop_words='english',
                                     tokenizer=tokenizer, ngram_range=(1, 3))
        print("DEBUG Created vectorizer")
        # Compute the Tf/Idf matrix of the corpus.
        tfidf_matrix = vectorizer.fit_transform(corpus.document_generator())
        # Get feature names from the fitted vectorizer.
        features = vectorizer.get_feature_names()
        print(tfidf_matrix.shape)
        print("DEBUG Computed tfidf")
        pickle.dump(tfidf_matrix, open('tfidf.pkl', 'wb'))
        pickle.dump(features, open('features.pkl', 'wb'))
        return tfidf_matrix

    def kmeans(self, corpus=None, tfidf_path=None, verbose=False):
        """ Applies kmeans clustering on a document collection.

        The clustering is performed in two steps creating two cluster layers. First,
        the collection is clustered into a big number of clusters. Next, the cluster
        centers of the created clusters are clustered resulting to K clusters.

        Args:
            corpus (:obj:'Corpus'): The Corpus object of the document collection.
                Defaults to None. Only used when no pre-computed Tf/Idf matrix is
                given.
            tfidf_path (str): The path to the file containing the Tf/Idf matrix .pkl file.
                Defaults to None and in this case the Tf/Idf matrix is calculated.
            verbose (bool): When True additional information will be printed.
                Defaults to False.

        Returns:
            layer2_kmodel (:obj:'Kmeans'): The second layer of clusters.

        """
        print("DEBUG Making cluster model")

        # Compute or load Tf/Idf matrix.
        if tfidf_path is None:
            tfidf_matrix = self.extract_tfidf(corpus)
            print(tfidf_matrix.shape)
        else:
            tfidf_matrix = pickle.load(open('tfidf.pkl', 'rb'))
            print(tfidf_matrix.shape)
            print('Loaded Tf/Idf matrix.')

        # Apply latent semantic analysis.
        if self.n_dimensions != None:
            print('Performing latent semantic analysis')
            svd = TruncatedSVD(self.n_dimensions)
            # Normalize SVD results for better clustering results.
            lsa = make_pipeline(svd, Normalizer(copy=False))
            tfidf_matrix = lsa.fit_transform(tfidf_matrix)
            print(tfidf_matrix.shape)
            print('DEBUG LSA completed')

        # Do the clustering.
        start_time = time.time()
        layer1_kmodel = KMeans(n_clusters=100, init='k-means++', n_init=1, max_iter=10,
                               verbose=True)
        layer2_kmodel = KMeans(n_clusters=self.n_clusters, init='k-means++', n_init=1, max_iter=10,
                               verbose=True)
        print('Clustering with %s' % layer1_kmodel)
        layer1_kmodel.fit(tfidf_matrix)
        print('Clustering with %s' % layer2_kmodel)
        layer2_kmodel.fit(layer1_kmodel.cluster_centers_)
        end_time = time.time()
        pickle.dump(layer1_kmodel, open('layer1_kmodel.pkl', 'wb'))
        pickle.dump(layer1_kmodel.cluster_centers_, open('centers.pkl', 'wb'))
        pickle.dump(layer2_kmodel, open('layer2_kmodel.pkl', 'wb'))
        #  cluster_labels = kmodel.labels_
        #  cluster_centers = kmodel.cluster_centers_

        if verbose:
            # Print some info.
            print("Top terms per cluster:")
            if self.n_dimensions != None:
                original_space_centroids = svd.inverse_transform(layer2_kmodel.cluster_centers_)
                order_centroids = original_space_centroids.argsort()[:, ::-1]
            else:
                order_centroids = layer2_kmodel.cluster_centers_.argsort()[:, ::-1]

            features = joblib.load('features.pkl')
            for i in range(self.n_clusters):
                print("Cluster %d:" % i, end='')
                for ind in order_centroids[i, :10]:
                    print(' %s' % features[ind], end='')
                    print()
        print('Clustering completed after ' + str(round((end_time-start_time)/60)) + "' "
              + str(round((end_time-start_time)%60)) + "''")
        return layer2_kmodel

    def hac(self, corpus=None, tfidf_path=None, verbose=False):
        """ Apply Hierarchical Agglomerative Clustering on a document collection.

        This method generates a hierarchical clustering tree for the collection and stops
        when there are K clusters without merging all the way up to a root node. The leaves
        of the tree are clusters consisting of single documents. The tree is then saved by
        saving the list of merges in a file.

        Each entry of this list contains the two tree nodes that were merged to create a
        new node and the new node's id. Node ids less than the number of leaves represent
        leaves, while node ids greater than the number of leaves indicate internal nodes.

        Args:
            corpus (:obj:'Corpus'): The Corpus object of the document collection.
                Defaults to None. Only used when no pre-computed Tf/Idf matrix is
                given.
            tfidf_path (str): The path to the file containing the Tf/Idf matrix .pkl file.
                Defaults to None and in this case the Tf/Idf matrix is calculated.
            verbose (bool): When True additional information will be printed.
                Defaults to False.

        Returns:
            hac_model (:obj:'AgglomerativeClustering'): The HAC model fitted on the
                document collection.

        """
        # Compute or load Tf/Idf matrix.
        if tfidf_path is None:
            tfidf_matrix = self.extract_tfidf(corpus)
            print(tfidf_matrix.shape)
        else:
            tfidf_matrix = pickle.load(open('tfidf.pkl', 'rb'))
            print(tfidf_matrix.shape)
            print('Loaded Tf/Idf matrix.')

        # Apply latent semantic analysis.
        if self.n_dimensions != None:
            print('Performing latent semantic analysis')
            svd = TruncatedSVD(self.n_dimensions)
            # Normalize SVD results for better clustering results.
            lsa = make_pipeline(svd, Normalizer(copy=False))
            tfidf_matrix = lsa.fit_transform(tfidf_matrix)

            print(tfidf_matrix.shape)
            print('DEBUG LSA completed')


        # Calculate documente distance matrix from Tf/Idf matrix
        dist = 1 - cosine_similarity(tfidf_matrix)
        print('DEBUG Computed distance matrix.')

        start_time = time.time()
        # Generate HAC model.
        hac_model = AgglomerativeClustering(linkage='ward', n_clusters=self.n_clusters)
        # Fit the model on the distance matrix.
        hac_model.fit(dist)
        end_time = time.time()
        joblib.dump(hac_model, 'hac.pkl')
        print('DEBUG Generated HAC model.')

        if verbose:
            # Visualize cluster model
            children = hac_model.children_
            merges = [{'node_id': node_id+len(dist),
                       'right': children[node_id, 0], 'left': children[node_id, 1]
                      } for node_id in range(0, len(children))]
            joblib.dump(merges, 'merges.pkl')
            joblib.dump(children, 'children.pkl')

            for merge_entry in enumerate(merges):
                print(merge_entry[1])

        print('Clustering completed after ' + str(round((end_time-start_time)/60)) + "' "
              + str(round((end_time-start_time)%60)) + "''")
        return hac_model