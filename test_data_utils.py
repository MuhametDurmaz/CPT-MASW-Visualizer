"""Run with: python -m unittest discover -s . -p 'test_*.py'"""
import unittest
from data_utils import read_csv, prepare, marker_sizes


class PreparationTests(unittest.TestCase):
    def test_categories_and_ids_survive_filtering(self):
        frame = read_csv(b'x,y,z,soil,id\n1,2,-1,Sand,001\n1,2,-2,Clay,002\nbad,2,-3,Silt,003\n1,2,-4,,004\n1,2,-5,2,005\n1,2,-6,#REF!,006\n')
        data, rejected = prepare(frame, ['x', 'y', 'z', 'soil'], categorical=True, id_column='id')
        self.assertEqual(rejected, 3)
        self.assertEqual(data.value.tolist(), ['Sand', 'Clay', '2'])
        self.assertEqual(data.id.tolist(), ['001', '002', '005'])

    def test_decimal_comma_and_blank_id(self):
        frame = read_csv(b'x;y;z;v;id\n1,5;2,5;-3,5;4,5;\n', 'Semicolon', ',')
        data, rejected = prepare(frame, ['x', 'y', 'z', 'v'], ',', id_column='id')
        self.assertEqual(rejected, 0)
        self.assertEqual(data.iloc[0].value, 4.5)
        self.assertEqual(data.iloc[0].id, '')

    def test_literal_na_category_and_id(self):
        frame = read_csv(b'x,y,z,soil,id\n1,2,3,NA,NA\n')
        data, rejected = prepare(frame, ['x', 'y', 'z', 'soil'], categorical=True, id_column='id')
        self.assertEqual(rejected, 0)
        self.assertEqual(data.iloc[0].value, 'NA')
        self.assertEqual(data.iloc[0].id, 'NA')

    def test_nonfinite_numeric_values_rejected(self):
        frame = read_csv(b'x,y,z,v\n1,2,3,4\n1,2,3,inf\n1,2,3,#REF!\n')
        data, rejected = prepare(frame, ['x', 'y', 'z', 'v'])
        self.assertEqual(len(data), 1)
        self.assertEqual(rejected, 2)
        self.assertEqual(marker_sizes([1, 4, None], 5), [5, 10, 5])

    def test_coordinates_must_be_distinct(self):
        frame = read_csv(b'x,y,z,v\n1,2,3,4\n')
        with self.assertRaises(ValueError):
            prepare(frame, ['x', 'x', 'z', 'v'])


if __name__ == '__main__':
    unittest.main()
