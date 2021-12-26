import os

from collections import Counter
from itertools import chain

from detectNew import Detect


class Review:
    def __init__(self):
        # define variables to hold pieces not detected
        self.not_detected = {'w': 0, 'wk': 0, 'b': 0, 'bk': 0, 'bl': 0, 'br': 0, 'tl': 0, 'tr': 0}
        # define variables to hold incorrectly detected pieces
        self.incorrectly_detected = {'w': 0, 'wk': 0, 'b': 0, 'bk': 0, 'bl': 0, 'br': 0, 'tl': 0, 'tr': 0}
        # define array for objects mistakenly detected
        self.mistakes = []
        # define list for duplicated corners
        self.dupes = []
        # define list for inconclusive detections where 2 objects have been detected in the same place
        self.unsure = []

    # 0 = b, 1 = bk, 2 = bl, 3 = br, 4 = tl, 5 = tr, 6 = w, 7 = wk
    def assess_damage(self, drawn, found, drawn_labels, found_labels):
        not_detected = drawn - found  # counts of classes not detected
        incorrectly_detected = found - drawn  # counts of classes wrongly detected
        if not_detected:  # count classes not detected
            self.add_values('not detected', not_detected)
        if incorrectly_detected:  # count incorrectly detected classes
            self.add_values('incorrect', incorrectly_detected)
            # Compare the incorrectly detected classes' label with the drawn labels checking for overlap
            self.find_overlaps(drawn_labels, found_labels)
            # check for duplicate corners. Format = <MaybeThis>, <OrThis>, <IThinkThis>
            self.check_duplicates(drawn_labels, found_labels)

    def find_overlaps(self, drawn_labels, found_labels):
        self.check_duplicates(drawn_labels, found_labels)
        # cycle through labels detected
        for found_label in found_labels:
            # get x, y of found_label
            x = found_label[1]
            y = found_label[2]
            # check for overlap with drawn labels
            for label in drawn_labels:
                # only look at the pieces
                if label[0] != found_label[0] and label[0] in [0, 1, 6, 7] and found_label[0] in [0, 1, 6, 7]:
                    # see if the x, y of the found label is in the bounding box
                    min_x, max_x, min_y, max_y = self.get_boundaries(label)
                    if min_x <= x <= max_x and min_y <= y <= max_y:
                        # overlap has occurred, implying that an object has been mistaken for another one
                        correct_class = label[0]
                        wrong_class = found_label[0]
                        self.mistakes.append([(KeyTranslator.translate_key(correct_class, True),
                                               KeyTranslator.translate_key(wrong_class, True))])

    def get_boundaries(self, label):
        min_x = label[1] - (label[3] / 2)
        max_x = label[1] + (label[3] / 2)
        min_y = label[2] - (label[4] / 2)
        max_y = label[2] + (label[4] / 2)
        return min_x, max_x, min_y, max_y

    def check_duplicates(self, drawn_labels, found_labels):
        # Find the image detections that have been duplicated
        for label in found_labels:
            checking_list = found_labels
            checking_list.remove(label)
            x = label[1]
            y = label[2]
            for label2 in checking_list:
                # Checking if the second label is an overlap
                min_x, max_x, min_y, max_y = self.get_boundaries(label2)
                if min_x <= x <= max_x and min_y <= y <= max_y:  # Is centre of label inside label2 box?
                    if label[0] == label2[0]:  # Same class
                        # A class has been duplicated
                        self.dupes.append([KeyTranslator.translate_key(label[0], True)])
                    elif label[0] not in [2, 3, 4, 5] and label2[0] not in [2, 3, 4, 5]:
                        # There is a discrepancy over which class should have been detected
                        if label[5] > label2[5]:
                            estimate = label
                        else:
                            estimate = label2
                        # need to see if the estimation was correct
                        match = self.match_label(drawn_labels, estimate)
                        self.unsure.append([(KeyTranslator.translate_key(label[0], True),
                                             KeyTranslator.translate_key(label2[0], True),
                                             KeyTranslator.translate_key(estimate[0], True),
                                             match)])

    def match_label(self, labels, estimate):
        x = estimate[1]
        y = estimate[2]
        for label in labels:
            min_x, max_x, min_y, max_y = self.get_boundaries(label)
            if label[0] in [0, 1, 6, 7] and min_x <= x <= max_x and min_y <= y <= max_y:  # Check for estimation overlap
                if estimate[0] == label[0]:
                    return True
                else:
                    return False

    def add_values(self, array_key, counter):
        if array_key == "incorrect":
            to_assign = self.incorrectly_detected
        else:
            to_assign = self.not_detected
        for item in counter:
            if item == 0:
                to_assign['b'] += counter[item]
            elif item == 1:
                to_assign['bk'] += counter[item]
            elif item == 2:
                to_assign['bl'] += counter[item]
            elif item == 3:
                to_assign['br'] += counter[item]
            elif item == 4:
                to_assign['tl'] += counter[item]
            elif item == 5:
                to_assign['tr'] += counter[item]
            elif item == 6:
                to_assign['w'] += counter[item]
            elif item == 7:
                to_assign['wk'] += counter[item]


def main():
    # Need to iterate through ../test/labels for all .txt files and match them with the results handed back
    directory = '../test/labels'
    drawn_labels = []
    for filename in sorted(os.listdir(directory)):
        with open((directory + '/' + filename), 'r') as file:
            labels = [[float(num) for num in line.split()] for line in file]  # Extract labels form file
        drawn_labels.append(labels)
    for label_set in drawn_labels:
        for label in label_set:
            label[0] = int(label[0])
    drawn_classes = get_classes(drawn_labels)  # extract classes

    detector = Detect()  # Start Yolov5 object detector
    print('Starting detection')
    returned_labels = detector.detect()  # Get returned classes and filenames
    print('Finished detection')

    returned_classes = get_classes(returned_labels)
    review = Review()
    perfect_matches = 0
    imperfect = 0
    total_count = Counter()

    for drawn, found, drawn_label_set, found_label_set in zip(drawn_classes, returned_classes, drawn_labels,
                                                              returned_labels):
        drawn_count = Counter(drawn)
        total_count += drawn_count
        found_count = Counter(found)

        if drawn_count != found_count:
            imperfect += 1
            review.assess_damage(drawn_count, found_count, drawn_label_set, found_label_set)
        else:
            perfect_matches += 1

    print('Perfect matches = ', perfect_matches)
    print('Imperfect estimations = ', imperfect, end='\n\n')
    print('Not detected:')
    print_review(total_count, review.not_detected, print_percentages=True)
    print('\n')
    print('Incorrectly detected ')
    print_review(total_count, review.incorrectly_detected, print_percentages=False)
    print('\n')
    print('Mistaken detections')
    mistakes = Counter(chain(*review.mistakes))
    print_mistakes(mistakes)
    print('\nDuplicated Classes')
    dupes = Counter(chain(*review.dupes))
    for item in dupes:
        print(item, 'was duplicated in the same place', dupes[item], 'times.')
    print('\nUnsure detections')
    unsure = Counter(chain(*review.unsure))
    print_unsure(unsure)


def print_unsure(unsure):
    for item in unsure:
        print(item[0], 'and', item[1], 'overlapped', unsure[item], 'times where', item[2],
              'was the best conf', end=' ')
        if item[3]:
            print('correctly.')
        else:
            print('incorrectly.')


def print_mistakes(mistakes):
    for item in mistakes:
        print(item[1], "should've been", item[0], mistakes[item], 'times.')


def get_classes(labels_arr):
    returned_classes = []
    for labels in labels_arr:
        class_list = []
        for label in labels:
            class_list.append(int(label[0]))
        returned_classes.append(class_list)
    return returned_classes


def print_review(total_count, wrong_counts, print_percentages):
    for item in wrong_counts:
        number = KeyTranslator.translate_key(item, False)
        if print_percentages:
            print(item, ':', wrong_counts[item], 'out of', total_count[number], end=' : ')
            if wrong_counts[item] > 0 and total_count[number] > 0:
                print("{:.2f}".format(100 - ((float(wrong_counts[item]) / float(total_count[number])) * 100.0)), end='')
                print('% success')
            else:
                print('100% success')
        else:
            print(item, ':', wrong_counts[item])


class KeyTranslator:
    # 0 = b, 1 = bk, 2 = bl, 3 = br, 4 = tl, 5 = tr, 6 = w, 7 = wk
    def translate_key(key, int_to_text):
        if int_to_text:
            if key == 0:
                return 'b'
            if key == 1:
                return 'bk'
            if key == 2:
                return 'bl'
            if key == 3:
                return 'br'
            if key == 4:
                return 'tl'
            if key == 5:
                return 'tr'
            if key == 6:
                return 'w'
            if key == 7:
                return 'wk'
        else:
            if key == 'b':
                return 0
            if key == 'bk':
                return 1
            if key == 'bl':
                return 2
            if key == 'br':
                return 3
            if key == 'tl':
                return 4
            if key == 'tr':
                return 5
            if key == 'w':
                return 6
            if key == 'wk':
                return 7


if __name__ == "__main__":
    main()
