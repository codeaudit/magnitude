# pylint: disable=no-self-use,invalid-name,no-value-for-parameter



from __future__ import division
from __future__ import absolute_import
import torch

from allennlp.common.testing.model_test_case import ModelTestCase
from allennlp.nn.decoding.chu_liu_edmonds import decode_mst

class BiaffineDependencyParserTest(ModelTestCase):

    def setUp(self):
        super(BiaffineDependencyParserTest, self).setUp()
        self.set_up_model(self.FIXTURES_ROOT / u"biaffine_dependency_parser" / u"experiment.json",
                          self.FIXTURES_ROOT / u"data" / u"dependencies.conllu")

    def test_dependency_parser_can_save_and_load(self):
        self.ensure_model_can_train_save_and_load(self.param_file)


    def test_mst_decoding_can_run_forward(self):
        self.model.use_mst_decoding_for_validation = True
        self.ensure_model_can_train_save_and_load(self.param_file)


    def test_batch_predictions_are_consistent(self):
        self.ensure_batch_predictions_are_consistent()

    def test_decode_runs(self):
        self.model.eval()
        training_tensors = self.dataset.as_tensor_dict()
        output_dict = self.model(**training_tensors)
        decode_output_dict = self.model.decode(output_dict)

        assert set(decode_output_dict.keys()) == set([u'arc_loss', u'tag_loss', u'loss',
                                                      u'predicted_dependencies', u'predicted_heads',
                                                      u'words', u'pos'])

    def test_mst_respects_no_outgoing_root_edges_constraint(self):
        # This energy tensor expresses the following relation:
        # energy[i,j] = "Score that i is the head of j". In this
        # case, we have heads pointing to their children.

        # We want to construct a case that has 2 children for the ROOT node,
        # because in a typical dependency parse there should only be one
        # word which has the ROOT as it's head.
        energy = torch.Tensor([[0, 9, 5],
                               [2, 0, 4],
                               [3, 1, 0]])

        length = torch.LongTensor([3])
        heads, _ = decode_mst(energy.numpy(), length.item(), has_labels=False)

        # This is the correct MST, but not desirable for dependency parsing.
        assert list(heads) == [-1, 0, 0]
        # If we run the decoding with the model, it should enforce
        # the constraint.
        heads_model, _ = self.model._run_mst_decoding(energy.view(1, 1, 3, 3), length) # pylint: disable=protected-access
        assert heads_model.tolist()[0] == [0, 0, 1]

    def test_mst_decodes_arc_labels_with_respect_to_unconstrained_scores(self):
        energy = torch.Tensor([[0, 2, 1],
                               [10, 0, 0.5],
                               [9, 0.2, 0]]).view(1, 1, 3, 3).expand(1, 2, 3, 3).contiguous()
        # Make the score for the root label for arcs to the root token be higher - it
        # will be masked for the MST, but we want to make sure that the tags are with
        # respect to the unmasked tensor. If the masking was incorrect, we would decode all
        # zeros as the labels, because torch takes the first index in the case that all the
        # values are equal, which would be the case if the labels were calculated from
        # the masked score.
        energy[:, 1, 0, :] = 3
        length = torch.LongTensor([3])
        heads, tags = self.model._run_mst_decoding(energy, length) # pylint: disable=protected-access
        assert heads.tolist()[0] == [0, 0, 1]
        assert tags.tolist()[0] == [0, 1, 0]
